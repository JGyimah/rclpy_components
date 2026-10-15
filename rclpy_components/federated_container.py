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

r"""
A container that routes each component to a container that can host it.

A container can host only components of its own language. A Python container
cannot load a C++ component, because that means dlopening a library through
``class_loader`` and getting back an ``rclcpp`` node, which no rclpy executor
can spin; a C++ container cannot host an rclpy node for the mirror-image
reason, since ``rclpy`` cannot be handed the context the container was built
on. Neither is a limitation this package can lift.

What it can do is make one node answer for both. This container serves the
composition contract itself and forwards each request to a real container
chosen by the language the component is registered for, keeping an id space of
its own so the components of both look like one set:

    ros2 run rclpy_components component_container_federated --ros-args \\
        -p python_container:=/rclpy_container -p cpp_container:=/cpp_container
    ros2 component load /federated_container my_package my_ns::CppNode
    ros2 component load /federated_container my_package my_package.talker:Talker
    ros2 component list

Call this federation rather than composition, because that is what it is: the
components run in the delegates' processes, not in this one. For the Python
ones that costs nothing, since rclpy has no intra-process communication to
lose. The C++ ones keep theirs among themselves inside their own container.
"""

import time

from composition_interfaces.srv import ListNodes, LoadNode, UnloadNode
import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from . import RESOURCE_GROUP
from .registry import components_in

#: The node name this container takes unless told otherwise.
DEFAULT_NAME = 'federated_container'

#: The resource group the C++ containers register their components under.
CPP_RESOURCE_GROUP = 'rclcpp_components'

#: The parameter naming the delegate for each language.
DELEGATE_PARAMETERS = {'python': 'python_container', 'cpp': 'cpp_container'}

#: How long to wait for a delegate to answer before giving up on it. A load
#: runs a component's constructor in the delegate, so this is as long as a
#: component may take to start, not just a round trip.
DELEGATE_TIMEOUT = 30.0

#: How long to wait for a delegate's services to appear, which is a round trip
#: plus discovery.
DISCOVERY_TIMEOUT = 5.0


class DelegateError(RuntimeError):
    """A delegate could not be reached, or did not answer in time."""


class FederatedContainer(Node):
    """Serves the composition contract by forwarding to other containers."""

    def __init__(self, name: str = DEFAULT_NAME) -> None:
        super().__init__(name)

        for parameter in DELEGATE_PARAMETERS.values():
            self.declare_parameter(parameter, '')

        #: Our own id for a component, against the delegate holding it.
        self._routes: dict[int, tuple[str, int, str]] = {}
        self._next_id = 1

        #: One client per delegate and service, made on first use. Not
        #: `_clients`, which rclpy's Node already uses for its own.
        self._delegates: dict[tuple[str, str], object] = {}

        # The three services share one mutually exclusive group, which
        # serialises the id counter and the route table. The clients need a
        # group of their own, and a reentrant one, because a service callback
        # blocks on a delegate's reply and that reply has to be delivered by
        # another thread of the executor while it does.
        self._serving = MutuallyExclusiveCallbackGroup()
        self._calling = ReentrantCallbackGroup()

        self.create_service(
            LoadNode, '~/_container/load_node', self._load, callback_group=self._serving
        )
        self.create_service(
            UnloadNode, '~/_container/unload_node', self._unload, callback_group=self._serving
        )
        self.create_service(
            ListNodes, '~/_container/list_nodes', self._list, callback_group=self._serving
        )

        self.get_logger().info(f'federated component container ready as {self.get_name()}')

    def _load(self, request, response):
        language = _language_of(request.package_name, request.plugin_name)

        if language is None:
            return self._refuse(
                response,
                f'no container language claims {request.plugin_name!r} in package '
                f'{request.package_name!r}: it is registered for neither '
                f'{RESOURCE_GROUP} nor {CPP_RESOURCE_GROUP}, and is not an '
                f"importable 'module:Class' target",
            )

        delegate = self.get_parameter(DELEGATE_PARAMETERS[language]).value

        if not delegate:
            return self._refuse(
                response,
                f'{request.plugin_name!r} is a {language} component and no {language} '
                f'container is configured; set the '
                f'{DELEGATE_PARAMETERS[language]} parameter to its node name',
            )

        if delegate == self.get_fully_qualified_name():
            return self._refuse(
                response,
                f'{DELEGATE_PARAMETERS[language]} names this container, which cannot '
                f'host a component itself',
            )

        try:
            result = self._ask(delegate, LoadNode, 'load_node', request)
        except DelegateError as e:
            return self._refuse(response, str(e))

        if not result.success:
            return self._refuse(response, f'{delegate}: {result.error_message}')

        unique_id = self._next_id
        self._next_id += 1
        self._routes[unique_id] = (delegate, result.unique_id, result.full_node_name)

        response.success = True
        response.full_node_name = result.full_node_name
        response.unique_id = unique_id

        self.get_logger().info(
            f'{delegate} loaded {result.full_node_name} as its {result.unique_id}, '
            f'which is {unique_id} here'
        )
        return response

    def _unload(self, request, response):
        route = self._routes.pop(request.unique_id, None)

        if route is None:
            return self._refuse(
                response, f'no component loaded with unique_id {request.unique_id}'
            )

        delegate, remote_id, full_name = route

        try:
            result = self._ask(
                delegate, UnloadNode, 'unload_node', UnloadNode.Request(unique_id=remote_id)
            )
        except DelegateError as e:
            # The component may well still be running, so the route is kept
            # rather than forgotten: this id remains the way to reach it.
            self._routes[request.unique_id] = route
            return self._refuse(response, str(e))

        if not result.success:
            # The delegate no longer has it under that id, whatever the reason,
            # so holding the route would only offer a dead handle.
            return self._refuse(response, f'{delegate}: {result.error_message}')

        response.success = True
        self.get_logger().info(f'{delegate} unloaded {full_name}')
        return response

    def _list(self, request, response):
        # The routes are what this container was asked to load, which is not
        # the same as everything the delegates hold: a component loaded by
        # talking to a delegate directly has no id here and is not listed.
        response.unique_ids = list(self._routes.keys())
        response.full_node_names = [full_name for _, _, full_name in self._routes.values()]
        return response

    def _ask(self, delegate: str, srv, service: str, request):
        """
        Put a request to a delegate and return its reply.

        Raises DelegateError if the delegate is not there to ask or does not
        answer, which are worth telling apart: the first is a container that
        was never running or was misnamed, the second one that is wedged.
        """
        client = self._client(delegate, srv, service)

        if not client.wait_for_service(timeout_sec=DISCOVERY_TIMEOUT):
            raise DelegateError(
                f'{delegate} is not offering {service} after {DISCOVERY_TIMEOUT}s; '
                f'is that container running?'
            )

        future = client.call_async(request)
        deadline = time.monotonic() + DELEGATE_TIMEOUT

        # Polled rather than waited on, so that nothing here depends on which
        # thread of the executor is delivering the reply.
        while not future.done():
            if time.monotonic() > deadline:
                future.cancel()
                raise DelegateError(
                    f'{delegate} did not answer {service} within {DELEGATE_TIMEOUT}s'
                )
            time.sleep(0.01)

        return future.result()

    def _client(self, delegate: str, srv, service: str):
        """Return the client for one service of one delegate, making it once."""
        key = (delegate, service)

        if key not in self._delegates:
            self._delegates[key] = self.create_client(
                srv, f'{delegate}/_container/{service}', callback_group=self._calling
            )

        return self._delegates[key]

    def _refuse(self, response, message: str):
        """Report a request the container will not complete."""
        self.get_logger().error(message)
        response.success = False
        response.error_message = message
        return response


def _language_of(package: str, plugin: str) -> str | None:
    """
    Return the language a component is registered for, or None for neither.

    A dotted import target is taken to be Python whether it is registered or
    not, which is the same latitude the rclpy container gives it.
    """
    if any(component.name == plugin for component in components_in(package)):
        return 'python'

    if ':' in plugin and '.' in plugin.split(':', 1)[0]:
        return 'python'

    if _registered_for_cpp(package, plugin):
        return 'cpp'

    return None


def _registered_for_cpp(package: str, plugin: str) -> bool:
    """
    Whether a package registers this component for a C++ container.

    The C++ group has the same line format as the rclpy one, so the same
    parser reads it; only the names are of use, since its targets are library
    paths for class_loader rather than import targets.
    """
    return any(
        component.name == plugin
        for component in components_in(package, group=CPP_RESOURCE_GROUP)
    )


def main(args=None):
    """Run a container that forwards components to other containers."""
    rclpy.init(args=args)

    container = FederatedContainer()
    # Multi-threaded of necessity, not for throughput: a service callback
    # blocks until a delegate replies, and another thread has to deliver it.
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
