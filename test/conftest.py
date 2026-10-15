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
Skip the container tests where the ROS runtime cannot host them.

The container needs a working rclpy and the composition_interfaces service
definitions. Deciding that here, with collect_ignore, means the test module
itself can use plain imports: a module-level pytest.importorskip aborts the
whole session on pytest 6.2.5 rather than skipping just that file.
"""

import importlib

collect_ignore = []

for module in ('rclpy', 'composition_interfaces', 'rcl_interfaces'):
    try:
        importlib.import_module(module)
    except Exception:  # noqa: BLE001 - any import failure means we cannot run
        collect_ignore.append('test_container.py')
        collect_ignore.append('test_federated_container.py')
        break
