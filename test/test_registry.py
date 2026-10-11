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
        'my_components::Talker;my_package.talker:Talker\n'
        'my_components::Listener;my_package.listener:Listener\n'
    )

    components = _parse('my_package', content)

    assert [c.name for c in components] == [
        'my_components::Talker',
        'my_components::Listener',
    ]
    assert components[0].target == 'my_package.talker:Talker'
    assert components[0].module == 'my_package.talker'
    assert components[0].class_name == 'Talker'
    assert components[0].package == 'my_package'


def test_parse_skips_a_malformed_line():
    # One bad entry must not hide the others.
    content = 'nonsense\nmy_components::Talker;my_package.talker:Talker\n'

    components = _parse('my_package', content)

    assert len(components) == 1
    assert components[0].name == 'my_components::Talker'


def test_parse_tolerates_whitespace():
    components = _parse('p', '  my_components::Talker ;  p.talker:Talker  \n')

    assert components[0].name == 'my_components::Talker'
    assert components[0].target == 'p.talker:Talker'


def test_resolve_falls_back_to_a_bare_target():
    # A package that was never registered can still be loaded by import path,
    # with the package name supplied as the module prefix.
    assert resolve('my_package', 'talker:Talker') == 'my_package.talker:Talker'


def test_resolve_accepts_a_fully_qualified_target():
    assert resolve('anything', 'my_package.talker:Talker') == 'my_package.talker:Talker'


def test_resolve_rejects_an_unregistered_plain_name():
    # Without a registry entry and without a colon there is nothing to import.
    with pytest.raises(LookupError, match='registers no component'):
        resolve('my_package', 'Talker')


def test_component_repr_names_both_halves():
    c = Component('p', 'my_components::Talker', 'p.talker:Talker')

    assert 'my_components::Talker' in repr(c)
    assert 'p.talker:Talker' in repr(c)
