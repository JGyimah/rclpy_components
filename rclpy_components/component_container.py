# Copyright 2026 Jude Gyimah
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
A component container for rclpy nodes.

``rclcpp_components`` provides a container process that loads C++ nodes into
itself on request. It has no rclpy counterpart, because it works by dlopening
a shared library through ``class_loader``, which has no Python equivalent. This
container closes that gap by serving the same three services over the same
names, so the stock ``ros2 component`` CLI drives it:

    ros2 run rclpy_components component_container_mt
    ros2 component load /rclpy_container my_package my_components::Talker
    ros2 component list
    ros2 component unload /rclpy_container 1

Loading imports the registered module and instantiates the class, then adds the
node to the container's executor so its callbacks run. Unloading removes it
from the executor and destroys it.

One difference from the C++ container is irreducible: unloading stops a
component but does not reclaim its code. Python has no ``dlclose``, and
dropping the module from ``sys.modules`` only clears the import cache — the
module object stays alive as long as anything references it.
"""

import importlib
import inspect
import traceback

from composition_interfaces.srv import ListNodes, LoadNode, UnloadNode
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter

from .registry import resolve

#: The node name the container takes unless told otherwise.
DEFAULT_NAME = 'rclpy_container'


class ComponentContainer(Node):
    """Hosts rclpy components and serves the composition_interfaces contract."""

    def __init__(self, name: str = DEFAULT_NAME) -> None:
        super().__init__(name)

        self._components: dict[int, tuple[str, Node]] = {}
        self._next_id = 1

        # These three share the node's default mutually-exclusive callback
        # group, which is what serialises access to the two fields above.
        self.create_service(LoadNode, '~/_container/load_node', self._load)
        self.create_service(UnloadNode, '~/_container/unload_node', self._unload)
        self.create_service(ListNodes, '~/_container/list_nodes', self._list)

        self.get_logger().info(f'rclpy component container ready as {self.get_name()}')

    # The executor the container itself was added to, which is also where
    # loaded components go.
    @property
    def _host(self):
        return self.executor

    def _load(self, request, response):
        # Each stage reports its own failure, so the caller is told whether the
        # component could not be found, not be imported, or not be constructed.
        try:
            target = resolve(request.package_name, request.plugin_name)
        except LookupError as e:
            return self._refuse(response, str(e))

        try:
            module_name, class_name = target.split(':', 1)
            cls = getattr(importlib.import_module(module_name), class_name)
        except Exception as e:  # noqa: BLE001 - reported to the caller
            return self._refuse(response, f'importing {target}: {e}', trace=True)

        try:
            instance = self._instantiate(cls, request)
        except Exception as e:  # noqa: BLE001 - reported to the caller
            return self._refuse(response, f'instantiating {target}: {e}', trace=True)

        if not isinstance(instance, Node):
            return self._refuse(
                response,
                f'{target} produced a {type(instance).__name__}, not an rclpy Node',
            )

        # The name is known only once the node exists, since remap rules are
        # applied during construction, so a clash can only be found by building
        # the component and throwing it away again.
        full_name = instance.get_fully_qualified_name()

        if self._name_taken(full_name):
            instance.destroy_node()
            return self._refuse(
                response, f'a node named {full_name} is already in this process'
            )

        self._host.add_node(instance)

        unique_id = self._next_id
        self._next_id += 1
        self._components[unique_id] = (full_name, instance)

        response.success = True
        response.full_node_name = full_name
        response.unique_id = unique_id

        self.get_logger().info(f'loaded {full_name} as {unique_id}')
        return response

    def _refuse(self, response, message: str, *, trace: bool = False):
        """Report a load the container will not complete."""
        if trace:
            self.get_logger().error(f'{message}\n{traceback.format_exc()}')
        else:
            self.get_logger().error(message)

        response.success = False
        response.error_message = message
        return response

    def _name_taken(self, full_name: str) -> bool:
        """Whether this fully qualified name is already in use in the process."""
        if full_name == self.get_fully_qualified_name():
            return True

        return any(name == full_name for name, _ in self._components.values())

    def _instantiate(self, cls, request):
        """
        Construct a component, passing the requested options when it can.

        A component that accepts ``**kwargs`` and forwards them to ``Node``
        receives the name, namespace, parameters and remappings the caller
        asked for. It does not have to accept a name: the name and namespace
        arrive as remap rules, so a component that names itself is renamed all
        the same. One that takes no arguments at all is constructed bare, and
        any options the caller sent are refused rather than silently dropped.
        """
        options = _node_options(request)

        if not _accepts_options(cls):
            asked_for = _requested(request)
            if asked_for:
                raise TypeError(
                    f'{cls.__name__} takes no constructor arguments, so it cannot apply '
                    f"{', '.join(asked_for)}; give it `def __init__(self, **kwargs)` "
                    f'forwarding to super().__init__()'
                )
            return cls()

        # A component's identity comes from the request, not from the
        # container's command line. Without this, a container started with
        # `-r __node:=x` renames every component it loads to x, because rclpy
        # applies global arguments to every node built in the process.
        options.setdefault('use_global_arguments', False)

        return cls(**options)

    def _unload(self, request, response):
        loaded = self._components.pop(request.unique_id, None)

        if loaded is None:
            response.success = False
            response.error_message = f'no component loaded with unique_id {request.unique_id}'
            self.get_logger().warning(response.error_message)
            return response

        _, instance = loaded

        self._host.remove_node(instance)
        instance.destroy_node()

        response.success = True
        self.get_logger().info(f'unloaded component {request.unique_id}')
        return response

    def _list(self, request, response):
        # The names are the ones recorded at load time rather than read back
        # from the nodes, so a component that destroyed itself cannot turn a
        # listing into an exception.
        response.unique_ids = list(self._components.keys())
        response.full_node_names = [name for name, _ in self._components.values()]
        return response


def _accepts_options(cls) -> bool:
    """Whether a component's constructor can be given node options."""
    # A class with no __init__ of its own inherits object's, whose signature is
    # (*args, **kwargs) — it would otherwise look like it accepts anything.
    if cls.__init__ is object.__init__:
        return False

    try:
        signature = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        return False

    return any(p.kind is p.VAR_KEYWORD for p in signature.parameters.values())


def _node_options(request) -> dict:
    """Translate a LoadNode request into rclpy Node constructor arguments."""
    options = {}

    if request.parameters:
        options['parameter_overrides'] = [
            Parameter.from_parameter_msg(p) for p in request.parameters
        ]

    # The name and namespace travel as remap rules rather than as constructor
    # arguments, which is how rclcpp_components applies them. Remapping happens
    # below the constructor, so it renames a component that passes a fixed name
    # of its own to Node — and `node_name=` cannot reach one of those at all,
    # since Node takes the name positionally and the call would be a TypeError
    # for two values of one argument.
    rules = []

    if request.node_name:
        rules.append(f'__node:={request.node_name}')

    if request.node_namespace:
        rules.append(f'__ns:={request.node_namespace}')

    rules += list(request.remap_rules)

    if rules:
        args = ['--ros-args']
        for rule in rules:
            args += ['-r', rule]
        options['cli_args'] = args

    return options


def _requested(request) -> list[str]:
    """Name the LoadNode fields a request actually set."""
    return [
        field
        for field, value in (
            ('node_name', request.node_name),
            ('node_namespace', request.node_namespace),
            ('parameters', request.parameters),
            ('remap_rules', request.remap_rules),
        )
        if value
    ]


def main(args=None):
    rclpy.init(args=args)

    container = ComponentContainer()
    executor = MultiThreadedExecutor()
    executor.add_node(container)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
