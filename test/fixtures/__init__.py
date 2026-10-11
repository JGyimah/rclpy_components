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
Component classes the container tests load.

These live under ``test`` rather than in the package because the package
installs a container, not components — ``rclcpp_components`` likewise ships
its containers and no example nodes. The directory is a package so the module
has a dotted name: the container's resolver reads an undotted target as a
module inside the requesting package, so ``components:Example`` would be
looked for in ``rclpy_components``.
"""
