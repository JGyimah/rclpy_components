from setuptools import find_packages, setup

package_name = 'rclpy_components'

setup(
    name=package_name,
    version='0.2.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='fr0b0',
    maintainer_email='jude.gyimah87@gmail.com',
    description='A component container for rclpy nodes.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # The first two names run the same multi-threaded container: a
            # single-threaded one would block its own load service behind a
            # component's callback.
            'component_container = rclpy_components.component_container:main',
            'component_container_mt = rclpy_components.component_container:main',
            # The isolated container gives each component a thread of its own,
            # so one that blocks in a callback holds up only itself.
            'component_container_isolated ='
            ' rclpy_components.component_container:isolated_main',
            # The federating container hosts nothing itself: it forwards each
            # component to a container of the right language.
            'component_container_federated ='
            ' rclpy_components.federated_container:main',
        ],
    },
)
