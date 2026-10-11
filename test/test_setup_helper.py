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

import os

import pytest

from rclpy_components import RESOURCE_GROUP
from rclpy_components.setup_helper import register_nodes, STAGING_DIR


def read_entry(tmp_path, package):
    with open(os.path.join(tmp_path, STAGING_DIR, package)) as f:
        return f.read()


def test_writes_one_line_per_component(tmp_path):
    entries = register_nodes(
        'py_plugin_executor',
        {
            'featx_plugin::Boot': 'py_plugin_executor.boot:Boot',
            'featx_plugin::InitChecks': 'py_plugin_executor.init_checks:InitChecks',
        },
        directory=str(tmp_path),
    )

    content = read_entry(tmp_path, 'py_plugin_executor')

    assert 'featx_plugin::Boot;py_plugin_executor.boot:Boot' in content
    assert 'featx_plugin::InitChecks;py_plugin_executor.init_checks:InitChecks' in content

    # And the data_files entry installs it where the registry looks.
    assert entries == [
        (
            f'share/ament_index/resource_index/{RESOURCE_GROUP}',
            [os.path.join(str(tmp_path), STAGING_DIR, 'py_plugin_executor')],
        )
    ]


def test_components_are_written_in_a_stable_order(tmp_path):
    # Two builds of the same package must produce the same file, or the
    # installed artifact churns for no reason.
    register_nodes('p', {'b::B': 'p.b:B', 'a::A': 'p.a:A'}, directory=str(tmp_path))
    first = read_entry(tmp_path, 'p')

    register_nodes('p', {'a::A': 'p.a:A', 'b::B': 'p.b:B'}, directory=str(tmp_path))
    assert read_entry(tmp_path, 'p') == first


def test_no_components_declares_nothing(tmp_path):
    # A package with no components should not install an empty resource file.
    assert register_nodes('p', {}, directory=str(tmp_path)) == []
    assert not os.path.exists(os.path.join(tmp_path, STAGING_DIR))


def test_rejects_a_target_without_a_class(tmp_path):
    # `module` alone is ambiguous; the container needs to know what to
    # instantiate, so this fails at build time rather than at load time.
    with pytest.raises(ValueError, match='module:Class'):
        register_nodes('p', {'p::A': 'p.a'}, directory=str(tmp_path))


def test_the_file_is_commented_for_a_human_reader(tmp_path):
    register_nodes('p', {'p::A': 'p.a:A'}, directory=str(tmp_path))

    content = read_entry(tmp_path, 'p')

    assert content.startswith('#')
    assert 'register_nodes' in content
