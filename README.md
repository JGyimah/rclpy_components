# rclpy_components

A component container for rclpy nodes.

`rclcpp_components` provides a container process that loads C++ nodes into
itself on request. It has no rclpy counterpart, because it works by dlopening a
shared library through `class_loader`, which has no Python equivalent. This
package closes that gap: a container that serves the same three
`composition_interfaces` services under the same names, so the stock `ros2
component` CLI drives it.

## Using the container

Start it, then load, list and unload components with the standard CLI:

```
ros2 run rclpy_components component_container_mt
```

```
ros2 component load /rclpy_container my_package my_package.talker:Talker
ros2 component list
ros2 component unload /rclpy_container 1
```

The container takes the node name `rclpy_container`. To run more than one, or
to place one in a namespace, remap it as usual:

```
ros2 run rclpy_components component_container_mt --ros-args -r __node:=my_container
```

`component_container` and `component_container_mt` are both installed and both
run the same multi-threaded container. A single-threaded one would block its
own load service behind a component's callback, so there is no single-threaded
variant to choose.

Loading imports the registered module, instantiates the class, and adds the
node to the container's executor so its callbacks run. Unloading removes it
from the executor and destroys it.

## Writing a component

A component is an ordinary rclpy `Node`. Accept `**kwargs` and forward them to
`Node`, and the name, namespace, parameters and remappings from the load
request reach the node:

```python
from rclpy.node import Node


class Talker(Node):

    def __init__(self, **kwargs):
        kwargs.setdefault('node_name', 'talker')
        super().__init__(**kwargs)
```

A component whose constructor takes no arguments can still be loaded, but it
cannot be given options. The container refuses such a request rather than
dropping the options silently, so prefer the shape above.
[`test/fixtures/components.py`](test/fixtures/components.py) has both, and a
plain class that is not a `Node` for contrast — the container refuses that one
outright, since there would be nothing to add to the executor. The package
installs a container and no components of its own, as `rclcpp_components`
does.

## Registering components

Registration is what lets a component be loaded by a short name instead of an
import path. It is the counterpart to `rclcpp_components_register_nodes()` in
CMake: call `register_nodes` from the package's `setup.py` and splice the
result into `data_files`.

```python
from rclpy_components.setup_helper import register_nodes

setup(
    name=package_name,
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        *register_nodes(package_name, {
            'my_components::Talker': 'my_package.talker:Talker',
        }),
    ],
    ...
)
```

Each entry maps the name the component is loaded by to the import target that
provides it, written `module:Class`. That installs a resource index entry under
the `rclpy_components` group, alongside the `rclcpp_components` entries the C++
containers read. With the registration above:

```
ros2 component load /rclpy_container my_package my_components::Talker
```

The generated file is staged in a `.rclpy_components/` directory beside
`setup.py`, which belongs in the package's `.gitignore`.

Registration is optional. A plugin name containing a colon is taken to be an
import target already, which is what the example at the top of this file
relies on, so an unregistered package can still be loaded by `module:Class`.

## One difference from the C++ container

Unloading stops a component but does not reclaim its code. Python has no
`dlclose`, and dropping the module from `sys.modules` only clears the import
cache — the module object stays alive as long as anything references it. A
component can be unloaded and loaded again, but the process does not shrink.

## Tests

```
python3 -m pytest test/
```

The suite includes `ament_copyright`, `ament_flake8` and `ament_pep257`, so
style is checked along with behaviour. The tests that need a live rclpy are
dropped from collection where the ROS runtime cannot be imported, so the suite
also runs outside a sourced workspace. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
