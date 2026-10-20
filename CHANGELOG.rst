^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Changelog for package rclpy_components
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

0.2.0 (2026-10-20)
------------------

Containers
~~~~~~~~~~

* Added ``component_container_isolated``, which spins each component on an
  executor and thread of its own, so a component that blocks in a callback
  holds up only itself. The isolation is of callbacks rather than of work:
  the GIL still serialises two components computing.
* Added ``component_container_federated``, which hosts nothing itself and
  forwards each request to a container that can host the component, chosen by
  the resource group the component is registered under. One node then answers
  for C++ and Python components together. This is federation and not
  composition: the components run in the delegates' processes.

Loading
~~~~~~~

* A component's name and namespace now arrive as ``__node:=`` and ``__ns:=``
  remap rules rather than as constructor arguments, which is how
  ``rclcpp_components`` applies them. A component that passes a name of its
  own to ``Node`` could not be loaded before this, because ``Node`` takes the
  name positionally and the call raised ``TypeError``.
* A load that would give two nodes in the process one fully qualified name is
  refused, and the component built to find that out is destroyed rather than
  left running and unlisted.
* ``LoadNode.log_level`` is applied to the component, and a value that is not
  a level is refused instead of raising inside the service.
* ``LoadNode.extra_arguments`` is honoured for the ``Node`` constructor flags
  ``allow_undeclared_parameters``,
  ``automatically_declare_parameters_from_overrides``, ``enable_rosout``,
  ``start_parameter_services`` and ``use_global_arguments``. An argument this
  container does not take is refused, and the two the C++ containers take that
  rclpy has no counterpart for are refused with the reason.
* Components are constructed on the container's own context rather than
  rclpy's global default.
* Each stage of a load reports its own failure, so a caller is told whether
  the component could not be found, could not be imported, or could not be
  constructed.
* Listings report the name recorded when a component was loaded rather than
  reading it back from the node, so a component that destroys itself cannot
  turn a listing into an exception.
* A lifecycle component is hosted like any other, and a test pins that its
  ``change_state`` and ``get_state`` services come up under the name the
  request gave it.

Package
~~~~~~~

* The example components moved to a test fixture. The package installs
  containers and no components of its own, as ``rclcpp_components`` does.
* ``registry.components_in`` takes the resource group to read, so the C++
  group can be read with the same parser.
* Added a README, covering the containers, the component contract,
  registration, and what unloading does and does not reclaim.
* Corrected the account of unloading: a module dropped from ``sys.modules``
  and left unreferenced *is* freed by Python, so what remains is this
  container keeping the module imported, a C extension that cannot be
  unloaded whatever anyone does, and a process that does not give the memory
  back. Measured: 60 load and unload cycles of one component move the
  resident set by under a megabyte, all of it on the first load.
* The editor configuration and the pytest cache are no longer tracked.

Tests and CI
~~~~~~~~~~~~

* Added CI: ``colcon build`` and ``colcon test`` on jazzy and rolling, a job
  that registers a component with no ROS runtime on the path, and a Windows
  job that reports rather than gates.
* Teardown in every fixture is bounded, so a stalled executor fails with a
  traceback instead of hanging a job.
* ``conftest.py`` names what each test module requires and reports the module,
  the requirement and the import error for anything it drops.
* CI fails when the suite runs fewer tests than it has, rather than reporting
  green on a run that shrank, and prints the environment rclpy was loaded
  from when a job breaks.
* Tests run outside the environment ``action-ros-ci`` exports, which arrived
  with a newline inside ``LD_LIBRARY_PATH`` and two paths concatenated in
  ``PYTHONPATH``, leaving rclpy unable to load ``librcl_action.so`` while the
  library was installed.

* Contributors: Jude Gyimah

0.1.0 (2026-10-11)
------------------

* First release: a component container for rclpy nodes, serving the three
  ``composition_interfaces`` services under the usual ``~/_container/*``
  names so that the stock ``ros2 component`` CLI drives it.
* Components are discovered through an ament resource index entry in the
  ``rclpy_components`` group, in the same ``name;target`` format
  ``rclcpp_components`` uses, with ``module:Class`` in place of a library
  path. ``setup_helper.register_nodes`` writes it from a package's
  ``setup.py``.
* Contributors: Jude Gyimah
