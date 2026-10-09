"""A component container for rclpy nodes.

This module deliberately imports nothing: ``setup_helper`` is used from a
package's ``setup.py`` at build time, where the ROS runtime may not be
importable, and it needs only the resource-group name from here.
"""

#: The ament resource index group rclpy components are registered under,
#: alongside the ``rclcpp_components`` entries the C++ containers read.
RESOURCE_GROUP = "rclpy_components"
