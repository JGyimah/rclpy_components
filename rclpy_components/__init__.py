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

This module deliberately imports nothing: ``setup_helper`` is used from a
package's ``setup.py`` at build time, where the ROS runtime may not be
importable, and it needs only the resource-group name from here.
"""

#: The ament resource index group rclpy components are registered under,
#: alongside the ``rclcpp_components`` entries the C++ containers read.
RESOURCE_GROUP = 'rclpy_components'
