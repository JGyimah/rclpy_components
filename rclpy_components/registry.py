"""Discovery of rclpy components through the ament resource index.

This mirrors how ``rclcpp_components`` finds C++ components. There, CMake
writes one resource file per package listing ``class_name;library_path``, and
the container reads it to turn a logical plugin name into something it can
load. Python has no shared libraries to point at, so the target is an import
path instead: ``class_name;module:Class``.

The resource index name is ``rclpy_components``, alongside the
``rclcpp_components`` entries the C++ containers read.
"""

from ament_index_python.resources import get_resource, get_resources, has_resource

from . import RESOURCE_GROUP


class Component:
    """One registered component: its declared name and where to import it."""

    def __init__(self, package: str, name: str, target: str) -> None:
        self.package = package
        self.name = name
        self.target = target

    @property
    def module(self) -> str:
        """The module half of the target."""
        return self.target.split(":", 1)[0]

    @property
    def class_name(self) -> str:
        """The class half of the target."""
        parts = self.target.split(":", 1)
        return parts[1] if len(parts) > 1 else ""

    def __repr__(self) -> str:
        return f"Component({self.package}/{self.name} -> {self.target})"


def components_in(package: str) -> list[Component]:
    """Return the components a single package registers.

    An unregistered package yields nothing rather than raising, since asking
    about a package that declares no components is a normal thing to do.
    """
    if not has_resource(RESOURCE_GROUP, package):
        return []

    content, _ = get_resource(RESOURCE_GROUP, package)
    return _parse(package, content)


def all_components() -> list[Component]:
    """Return every component registered by every package on the path."""
    out: list[Component] = []
    for package in sorted(get_resources(RESOURCE_GROUP)):
        out.extend(components_in(package))
    return out


def resolve(package: str, name: str) -> str:
    """Turn a package and plugin name into an import target.

    The registry is consulted first, so a component can be loaded by the name
    it registered. Failing that, the name is taken to be an import target
    already, which keeps ``module:Class`` working for a package that has not
    been registered.
    """
    for component in components_in(package):
        if component.name == name:
            return component.target

    if ":" in name:
        return name if "." in name.split(":", 1)[0] else f"{package}.{name}"

    raise LookupError(
        f"package {package!r} registers no component named {name!r}; "
        f"either register it or load it as 'module:Class'"
    )


def _parse(package: str, content: str) -> list[Component]:
    out = []

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        name, _, target = line.partition(";")
        if not target:
            # A malformed line is skipped rather than failing the whole
            # package: one bad entry should not hide the others.
            continue

        out.append(Component(package, name.strip(), target.strip()))

    return out
