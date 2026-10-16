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
Components the container tests load, one per constructor shape it meets.

A component that accepts ``**kwargs`` and forwards them to ``Node`` can be
given the name, namespace, parameters and remappings from a ``LoadNode``
request. One that takes no arguments cannot, and the container says so rather
than dropping the options silently — so a real component should look like
:class:`Example`.
"""

import threading

from rclpy.lifecycle import LifecycleNode
from rclpy.node import Node


class Example(Node):
    """The shape to copy: node options reach the node."""

    def __init__(self, **kwargs):
        kwargs.setdefault('node_name', 'example')
        super().__init__(**kwargs)

        self.get_logger().info(f'{self.get_name()} loaded')


class FixedName(Node):
    """A component that names itself, which only a remap rule can rename."""

    def __init__(self, **kwargs):
        super().__init__('fixed_name', **kwargs)

        self.get_logger().info(f'{self.get_name()} loaded')


class Lifecycle(LifecycleNode):
    """
    A managed component, which the container hosts like any other.

    A LifecycleNode is a Node, so nothing in the container knows the
    difference; what the test pins is that its state machine survives being
    loaded, since a component is constructed differently from a node a process
    creates for itself.
    """

    def __init__(self, **kwargs):
        super().__init__('lifecycle', **kwargs)


class NoOptions(Node):
    """A component that cannot be given options, for contrast."""

    def __init__(self):
        super().__init__('no_options')

        self.get_logger().info('no_options loaded')


class Blocking(Node):
    """A component whose timer callback never returns, to test isolation."""

    def __init__(self, **kwargs):
        super().__init__('blocking', **kwargs)

        self.create_timer(0.0, self._wedge)

    def _wedge(self):
        self.get_logger().info('wedging this executor')
        threading.Event().wait()


class NotAComponent:
    """
    A plain class, registered by mistake.

    The container refuses this rather than hosting it: a component has to be
    an rclpy Node for there to be anything to add to the executor.
    """
