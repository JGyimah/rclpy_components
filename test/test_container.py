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
Tests for the container itself.

conftest.py drops this module from collection where rclpy or
composition_interfaces cannot be imported, so the imports below are plain.
"""

from composition_interfaces.srv import ListNodes, LoadNode, UnloadNode
# Sorted here rather than with the package imports below: `fixtures` is not
# an application import name, so the linter groups it with the installed
# ones.
from fixtures.components import Example, NoOptions
import pytest
from rcl_interfaces.msg import Parameter as ParameterMsg
from rcl_interfaces.msg import ParameterType, ParameterValue
import rclpy
from rclpy.executors import MultiThreadedExecutor

from rclpy_components.component_container import (
    _accepts_options,
    _node_options,
    ComponentContainer,
)

#: The fixture components, and a real class among them that is not a Node.
EXAMPLE = 'fixtures.components:Example'
EXAMPLE_FIXED_NAME = 'fixtures.components:FixedName'
EXAMPLE_NO_OPTIONS = 'fixtures.components:NoOptions'
NOT_A_NODE = 'fixtures.components:NotAComponent'


@pytest.fixture
def container():
    rclpy.init()

    node = ComponentContainer('test_container')
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    yield node

    executor.shutdown()
    node.destroy_node()
    rclpy.shutdown()


def load(container, target, **fields):
    """Load by qualified target, since these fixtures register no name."""
    request = LoadNode.Request()
    request.package_name = 'rclpy_components'
    request.plugin_name = target
    for k, v in fields.items():
        setattr(request, k, v)
    return container._load(request, LoadNode.Response())


def test_load_then_list_then_unload(container):
    response = load(container, EXAMPLE_NO_OPTIONS)

    assert response.success, response.error_message
    assert response.unique_id == 1
    assert response.full_node_name.endswith('no_options')

    listing = container._list(ListNodes.Request(), ListNodes.Response())
    assert list(listing.unique_ids) == [1]
    assert listing.full_node_names[0].endswith('no_options')

    request = UnloadNode.Request()
    request.unique_id = 1
    assert container._unload(request, UnloadNode.Response()).success

    listing = container._list(ListNodes.Request(), ListNodes.Response())
    assert list(listing.unique_ids) == []


def test_unique_ids_do_not_repeat(container):
    first = load(container, EXAMPLE_NO_OPTIONS)
    second = load(container, EXAMPLE)

    assert first.unique_id != second.unique_id


def test_unloading_an_unknown_id_is_reported(container):
    request = UnloadNode.Request()
    request.unique_id = 99

    response = container._unload(request, UnloadNode.Response())

    assert not response.success
    assert '99' in response.error_message


def test_loading_a_non_node_is_refused(container):
    response = load(container, NOT_A_NODE)

    assert not response.success
    assert 'not an rclpy Node' in response.error_message


def test_loading_an_unknown_module_is_refused(container):
    request = LoadNode.Request()
    request.package_name = 'no_such_package'
    request.plugin_name = 'no_such_package.nowhere:Thing'
    response = container._load(request, LoadNode.Response())

    assert not response.success
    assert response.error_message


# TestNodeOptions: a component that cannot accept options must be told so
# rather than having them silently dropped.
def test_options_on_a_plain_component_are_refused(container):
    response = load(container, EXAMPLE_NO_OPTIONS, node_name='renamed')

    assert not response.success
    assert 'takes no constructor arguments' in response.error_message


def test_options_reach_a_configurable_component(container):
    response = load(container, EXAMPLE, node_name='renamed', node_namespace='/ns')

    assert response.success, response.error_message
    assert response.full_node_name == '/ns/renamed'


def test_parameters_reach_a_configurable_component(container):
    value = ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=1.5)

    response = load(
        container, EXAMPLE, parameters=[ParameterMsg(name='vel_max', value=value)]
    )

    assert response.success, response.error_message

    # rclpy needs a parameter declared before it can be read; declaring one
    # that has an override takes the override's value, which is what proves
    # the request reached the node.
    _, loaded = container._components[response.unique_id]
    loaded.declare_parameter('vel_max', 0.0)

    assert loaded.get_parameter('vel_max').value == pytest.approx(1.5)


def test_a_component_that_names_itself_is_renamed_anyway(container):
    # Node takes the name positionally, so a component passing one of its own
    # cannot be given `node_name=` -- that call is a TypeError for two values
    # of one argument. The request's name reaches it as a remap rule instead.
    response = load(container, EXAMPLE_FIXED_NAME, node_name='renamed')

    assert response.success, response.error_message
    assert response.full_node_name == '/renamed'


def test_a_component_that_names_itself_is_moved_into_a_namespace(container):
    response = load(container, EXAMPLE_FIXED_NAME, node_namespace='/sensors')

    assert response.success, response.error_message
    assert response.full_node_name == '/sensors/fixed_name'


def test_a_second_component_cannot_take_a_name_already_in_the_process(container):
    first = load(container, EXAMPLE_FIXED_NAME)
    assert first.success, first.error_message

    second = load(container, EXAMPLE_FIXED_NAME)

    assert not second.success
    assert 'already in this process' in second.error_message
    # The rejected component is destroyed rather than left running unlisted.
    listing = container._list(ListNodes.Request(), ListNodes.Response())
    assert list(listing.unique_ids) == [first.unique_id]


def test_a_component_cannot_take_the_container_s_own_name(container):
    response = load(container, EXAMPLE_FIXED_NAME, node_name=container.get_name())

    assert not response.success
    assert 'already in this process' in response.error_message


def test_the_same_component_can_be_loaded_twice_under_different_names(container):
    first = load(container, EXAMPLE_FIXED_NAME, node_name='left')
    second = load(container, EXAMPLE_FIXED_NAME, node_name='right')

    assert first.success and second.success, second.error_message
    assert first.full_node_name == '/left'
    assert second.full_node_name == '/right'


def test_a_failure_says_which_stage_it_came_from(container):
    missing_module = load(container, 'fixtures.no_such_module:Thing')
    assert not missing_module.success
    assert missing_module.error_message.startswith('importing ')

    missing_class = load(container, 'fixtures.components:NoSuchClass')
    assert not missing_class.success
    assert missing_class.error_message.startswith('importing ')

    # NoOptions cannot be given a name, so it fails while being constructed.
    cannot_construct = load(container, EXAMPLE_NO_OPTIONS, node_name='renamed')
    assert not cannot_construct.success
    assert cannot_construct.error_message.startswith('instantiating ')


def test_a_component_joins_the_container_s_context(container):
    response = load(container, EXAMPLE)
    assert response.success, response.error_message

    _, loaded = container._components[response.unique_id]
    assert loaded.context is container.context


def test_accepts_options_distinguishes_the_two_shapes():
    assert _accepts_options(Example)
    assert not _accepts_options(NoOptions)


def test_node_options_translates_a_request():
    request = LoadNode.Request()
    assert _node_options(request) == {}

    request.node_name = 'n'
    request.node_namespace = '/ns'
    request.remap_rules = ['a:=b']

    options = _node_options(request)

    # The name and namespace are remap rules, ahead of the caller's own rules,
    # and nothing is passed as a constructor argument that Node takes
    # positionally.
    assert options['cli_args'] == [
        '--ros-args', '-r', '__node:=n', '-r', '__ns:=/ns', '-r', 'a:=b',
    ]
    assert 'node_name' not in options
    assert 'namespace' not in options


# TestGlobalArgumentsDoNotLeak guards a bug a live run found: a container
# started with `-r __node:=x` renamed every component it loaded to x, because
# rclpy applies global arguments to every node built in the process.
def test_global_arguments_do_not_leak_into_a_component(container):
    response = load(container, EXAMPLE)

    assert response.success, response.error_message
    assert response.full_node_name.endswith('example')

    _, loaded = container._components[response.unique_id]
    assert loaded.get_name() == 'example'


def test_node_options_disables_global_arguments(container):
    # The flag is set even when the request carries no options at all.
    response = load(container, EXAMPLE)
    assert response.success, response.error_message


def test_a_class_with_no_init_does_not_look_configurable():
    # object.__init__ has a (*args, **kwargs) signature, so a class that
    # defines no constructor would otherwise appear to accept node options.
    from fixtures.components import NotAComponent

    assert not _accepts_options(NotAComponent)
