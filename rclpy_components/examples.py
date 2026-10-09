"""Minimal components, showing the two constructor shapes a container meets.

A component that accepts ``**kwargs`` and forwards them to ``Node`` can be
given the name, namespace, parameters and remappings from a ``LoadNode``
request. One that takes no arguments cannot, and the container says so rather
than dropping the options silently — so prefer :class:`Example`.
"""

from rclpy.node import Node


class Example(Node):
    """The shape to copy: node options reach the node."""

    def __init__(self, **kwargs):
        kwargs.setdefault("node_name", "example")
        super().__init__(**kwargs)

        self.get_logger().info(f"{self.get_name()} loaded")


class NoOptions(Node):
    """A component that cannot be given options, for contrast."""

    def __init__(self):
        super().__init__("no_options")

        self.get_logger().info("no_options loaded")


class NotAComponent:
    """A plain class, registered by mistake.

    The container refuses this rather than hosting it: a component has to be
    an rclpy Node for there to be anything to add to the executor.
    """
