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
    ros2 component load /rclpy_container py_plugin_executor featx_plugin::Boot
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

        self._components: dict[int, Node] = {}
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
        try:
            target = resolve(request.package_name, request.plugin_name)
            module_name, class_name = target.split(':', 1)

            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)

            instance = self._instantiate(cls, request)

            if not isinstance(instance, Node):
                raise TypeError(
                    f'{target} produced a {type(instance).__name__}, not an rclpy Node'
                )

            self._host.add_node(instance)

            unique_id = self._next_id
            self._next_id += 1
            self._components[unique_id] = instance

            response.success = True
            response.full_node_name = instance.get_fully_qualified_name()
            response.unique_id = unique_id

            self.get_logger().info(f'loaded {response.full_node_name} as {unique_id}')

        except Exception as e:  # noqa: BLE001 - reported to the caller
            self.get_logger().error(f'loading {request.plugin_name}: {traceback.format_exc()}')
            response.success = False
            response.error_message = str(e)

        return response

    def _instantiate(self, cls, request):
        """
        Construct a component, passing the requested options when it can.

        A component that accepts ``**kwargs`` and forwards them to ``Node``
        receives the name, namespace, parameters and remappings the caller
        asked for. One that takes no arguments is constructed bare, and any
        options the caller sent are refused rather than silently dropped.
        """
        options = _node_options(request)

        if not _accepts_options(cls):
            if options:
                raise TypeError(
                    f'{cls.__name__} takes no constructor arguments, so it cannot apply '
                    f"{', '.join(sorted(options))}; give it `def __init__(self, **kwargs)` "
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
        instance = self._components.pop(request.unique_id, None)

        if instance is None:
            response.success = False
            response.error_message = f'no component loaded with unique_id {request.unique_id}'
            self.get_logger().warning(response.error_message)
            return response

        self._host.remove_node(instance)
        instance.destroy_node()

        response.success = True
        self.get_logger().info(f'unloaded component {request.unique_id}')
        return response

    def _list(self, request, response):
        response.unique_ids = list(self._components.keys())
        response.full_node_names = [
            instance.get_fully_qualified_name() for instance in self._components.values()
        ]
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

    if request.node_name:
        options['node_name'] = request.node_name

    if request.node_namespace:
        options['namespace'] = request.node_namespace

    if request.parameters:
        options['parameter_overrides'] = [
            Parameter.from_parameter_msg(p) for p in request.parameters
        ]

    if request.remap_rules:
        args = ['--ros-args']
        for rule in request.remap_rules:
            args += ['-r', rule]
        options['cli_args'] = args

    return options


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
