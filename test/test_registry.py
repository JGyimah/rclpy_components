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

import pytest

from rclpy_components import RESOURCE_GROUP
from rclpy_components.registry import _parse, Component, resolve


def test_resource_group_matches_the_package_name():
    # The container and the setup helper must agree, and the group is also the
    # directory name under resource_index, so it is worth pinning.
    assert RESOURCE_GROUP == 'rclpy_components'


def test_parse_reads_name_and_target():
    content = (
        '# a comment\n'
        '\n'
        'featx_plugin::Boot;py_plugin_executor.boot:Boot\n'
        'featx_plugin::InitChecks;py_plugin_executor.init_checks:InitChecks\n'
    )

    components = _parse('py_plugin_executor', content)

    assert [c.name for c in components] == [
        'featx_plugin::Boot',
        'featx_plugin::InitChecks',
    ]
    assert components[0].target == 'py_plugin_executor.boot:Boot'
    assert components[0].module == 'py_plugin_executor.boot'
    assert components[0].class_name == 'Boot'
    assert components[0].package == 'py_plugin_executor'


def test_parse_skips_a_malformed_line():
    # One bad entry must not hide the others.
    content = 'nonsense\nfeatx_plugin::Boot;py_plugin_executor.boot:Boot\n'

    components = _parse('py_plugin_executor', content)

    assert len(components) == 1
    assert components[0].name == 'featx_plugin::Boot'


def test_parse_tolerates_whitespace():
    components = _parse('p', '  featx_plugin::Boot ;  p.boot:Boot  \n')

    assert components[0].name == 'featx_plugin::Boot'
    assert components[0].target == 'p.boot:Boot'


def test_resolve_falls_back_to_a_bare_target():
    # A package that was never registered can still be loaded by import path,
    # with the package name supplied as the module prefix.
    assert resolve('py_plugin_executor', 'boot:Boot') == 'py_plugin_executor.boot:Boot'


def test_resolve_accepts_a_fully_qualified_target():
    assert resolve('anything', 'py_plugin_executor.boot:Boot') == 'py_plugin_executor.boot:Boot'


def test_resolve_rejects_an_unregistered_plain_name():
    # Without a registry entry and without a colon there is nothing to import.
    with pytest.raises(LookupError, match='registers no component'):
        resolve('py_plugin_executor', 'Boot')


def test_component_repr_names_both_halves():
    c = Component('p', 'featx_plugin::Boot', 'p.boot:Boot')

    assert 'featx_plugin::Boot' in repr(c)
    assert 'p.boot:Boot' in repr(c)
