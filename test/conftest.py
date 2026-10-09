"""Skip the container tests where the ROS runtime cannot host them.

The container needs a working rclpy and the composition_interfaces service
definitions. Deciding that here, with collect_ignore, means the test module
itself can use plain imports: a module-level pytest.importorskip aborts the
whole session on pytest 6.2.5 rather than skipping just that file.
"""

import importlib

collect_ignore = []

for module in ("rclpy", "composition_interfaces", "rcl_interfaces"):
    try:
        importlib.import_module(module)
    except Exception:  # noqa: BLE001 - any import failure means we cannot run
        collect_ignore.append("test_container.py")
        break
