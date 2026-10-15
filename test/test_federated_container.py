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
Tests for the federating container.

The routing tests need no delegate. The one that forwards runs a real rclpy
container beside the federator and lets them talk over the middleware, since
what is worth testing is the forwarding, not a mock of it.

conftest.py drops this module from collection where rclpy cannot be imported.
"""

import os
import threading

from composition_interfaces.srv import ListNodes, LoadNode, UnloadNode
import pytest
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.parameter import Parameter

from rclpy_components.component_container import ComponentContainer
from rclpy_components.federated_container import (
    _language_of,
    CPP_RESOURCE_GROUP,
    FederatedContainer,
)

EXAMPLE = 'fixtures.components:Example'

#: Long enough for discovery and a reply on a loopback, short enough that a
#: wedged test fails rather than hanging the suite.
PATIENCE = 20.0


@pytest.fixture
def federator():
    rclpy.init()

    node = FederatedContainer('test_federator')
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    yield node

    executor.shutdown(timeout_sec=PATIENCE)
    node.destroy_node()
    rclpy.shutdown()


@pytest.fixture
def federation():
    """Spin a federator beside a real rclpy container to delegate to."""
    rclpy.init()

    delegate = ComponentContainer('test_delegate')
    federator = FederatedContainer('test_federator')
    federator.set_parameters(
        [Parameter('python_container', value=delegate.get_fully_qualified_name())]
    )

    executor = MultiThreadedExecutor()
    executor.add_node(delegate)
    executor.add_node(federator)

    spinning = threading.Thread(target=executor.spin, daemon=True)
    spinning.start()

    yield federator, delegate

    executor.shutdown(timeout_sec=PATIENCE)
    spinning.join(timeout=PATIENCE)
    assert not spinning.is_alive(), 'the executor did not stop spinning'

    delegate.unload_all()
    federator.destroy_node()
    delegate.destroy_node()
    rclpy.shutdown()


def load(container, target, **fields):
    request = LoadNode.Request()
    request.package_name = 'rclpy_components'
    request.plugin_name = target
    for name, value in fields.items():
        setattr(request, name, value)
    return container._load(request, LoadNode.Response())


def test_a_dotted_target_is_python(fake_resources):
    assert _language_of('rclpy_components', EXAMPLE) == 'python'


def test_a_name_registered_for_cpp_is_cpp(fake_resources):
    assert _language_of('cpp_package', 'cpp_ns::CppNode') == 'cpp'


def test_a_name_registered_for_neither_is_neither(fake_resources):
    assert _language_of('cpp_package', 'cpp_ns::Absent') is None
    assert _language_of('no_such_package', 'Whatever') is None


def test_a_component_of_no_known_language_is_refused(federator):
    response = load(federator, 'NotRegisteredAnywhere')

    assert not response.success
    assert 'no container language claims' in response.error_message


def test_a_python_component_needs_a_python_container(federator):
    response = load(federator, EXAMPLE)

    assert not response.success
    assert 'no python container is configured' in response.error_message
    assert 'python_container' in response.error_message


def test_the_federator_refuses_to_delegate_to_itself(federator):
    federator.set_parameters(
        [Parameter('python_container', value=federator.get_fully_qualified_name())]
    )

    response = load(federator, EXAMPLE)

    assert not response.success
    assert 'cannot host a component itself' in response.error_message


def test_a_delegate_that_is_not_running_says_so(federator):
    federator.set_parameters([Parameter('python_container', value='/absent_container')])

    response = load(federator, EXAMPLE)

    assert not response.success
    # The container was never there to ask, which is not the same as a wedged
    # one that never replied.
    assert 'is not offering load_node' in response.error_message
    assert 'is that container running?' in response.error_message


def test_unloading_an_id_it_never_issued_is_refused(federator):
    response = federator._unload(
        UnloadNode.Request(unique_id=42), UnloadNode.Response()
    )

    assert not response.success
    assert 'no component loaded with unique_id 42' in response.error_message


def test_a_load_is_forwarded_listed_and_unloaded(federation):
    federator, delegate = federation

    loaded = load(federator, EXAMPLE)
    assert loaded.success, loaded.error_message
    assert loaded.full_node_name.endswith('example')

    # The delegate is the one actually holding it.
    held = delegate._list(ListNodes.Request(), ListNodes.Response())
    assert list(held.full_node_names) == [loaded.full_node_name]

    # The federator lists it under an id of its own.
    listing = federator._list(ListNodes.Request(), ListNodes.Response())
    assert list(listing.unique_ids) == [loaded.unique_id]
    assert list(listing.full_node_names) == [loaded.full_node_name]

    unloaded = federator._unload(
        UnloadNode.Request(unique_id=loaded.unique_id), UnloadNode.Response()
    )
    assert unloaded.success, unloaded.error_message

    # The id arrays are rosidl sequences, so they are compared as lists.
    assert list(delegate._list(ListNodes.Request(), ListNodes.Response()).unique_ids) == []
    assert list(federator._list(ListNodes.Request(), ListNodes.Response()).unique_ids) == []


def test_ids_are_the_federators_own_not_the_delegates(federation):
    federator, delegate = federation

    first = load(federator, EXAMPLE, node_name='one')
    second = load(federator, EXAMPLE, node_name='two')

    assert first.success and second.success, second.error_message
    # Both sides count from 1, so the ids only coincide while nothing has been
    # loaded into the delegate by anyone else. What matters is that the
    # federator answers for its own.
    assert {first.unique_id, second.unique_id} == {1, 2}
    assert set(federator._routes) == {first.unique_id, second.unique_id}


def test_a_delegates_refusal_is_reported_with_its_name(federation):
    federator, delegate = federation

    # The delegate refuses a second component of the same name.
    first = load(federator, EXAMPLE)
    assert first.success, first.error_message

    second = load(federator, EXAMPLE)

    assert not second.success
    assert delegate.get_fully_qualified_name() in second.error_message
    assert 'already in this process' in second.error_message


@pytest.fixture
def fake_resources(tmp_path, monkeypatch):
    """Put a package registered for the C++ group on the resource path."""
    index = tmp_path / 'share' / 'ament_index' / 'resource_index'

    packages = index / 'packages'
    packages.mkdir(parents=True)
    (packages / 'cpp_package').write_text('')

    group = index / CPP_RESOURCE_GROUP
    group.mkdir(parents=True)
    (group / 'cpp_package').write_text('cpp_ns::CppNode;lib/libcpp_node.so\n')

    monkeypatch.setenv(
        'AMENT_PREFIX_PATH', f'{tmp_path}{os.pathsep}{os.environ.get("AMENT_PREFIX_PATH", "")}'
    )
    return tmp_path
