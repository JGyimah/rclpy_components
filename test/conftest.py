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
Drop the test modules whose dependencies are not installed.

Only the setup helper runs with nothing from ROS on the path, which is the
point of it: a plugin package calls it from its own setup.py, where the
runtime may not be importable yet. Everything else needs the runtime, the
index, or the linters, and says so below.

Deciding it here, with collect_ignore, means each test module can use plain
imports: a module-level pytest.importorskip aborts the whole session on
pytest 6.2.5 rather than skipping just that file.

A module dropped for a missing dependency is silence, not a pass, so an
environment that is meant to have ROS has to be checked for it elsewhere —
in CI, before the tests run — or a broken one reports as a short green run.
"""

import importlib

#: What each test module cannot be collected without.
REQUIREMENTS = {
    'test_container.py': (
        'rclpy',
        'rclpy.lifecycle',
        'composition_interfaces',
        'rcl_interfaces',
    ),
    'test_federated_container.py': (
        'rclpy',
        'composition_interfaces',
    ),
    'test_registry.py': ('ament_index_python',),
    'test_copyright.py': ('ament_copyright',),
    'test_flake8.py': ('ament_flake8',),
    'test_pep257.py': ('ament_pep257',),
}

collect_ignore = []

for module, requirements in REQUIREMENTS.items():
    for requirement in requirements:
        try:
            importlib.import_module(requirement)
        except Exception:  # noqa: BLE001 - any import failure means we cannot run
            collect_ignore.append(module)
            break
