from setuptools import setup

package_name = 'ot2_driver_pkg'

install_requires = []
with open('requirements.txt') as reqs:
    for line in reqs.readlines():
        req = line.strip()
        if not req or req.startswith('#'):
            continue
        install_requires.append(req)

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name, 'database', 'protocol_handler', 'zeroMQ_OT2', 'ZeroMQ_External'],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires = install_requires,
    zip_safe=True,
    maintainer='Doga Ozgulbas and Alan Wang',
    maintainer_email='dozgulbas@anl.gov',
    description='Driver for the OT2',
    license='MIT License',
    entry_points={
        'console_scripts': [
            'ot2_driver = ot2_driver_pkg.ot2_driver:main_null',
            'database_functions = database.database_functions:main_null',
            'connect = database.connect:main_null',
            'protocol_parser = protocol_handler.protocol_parser:main_null',
            'protocol_handling_client = protocol_handler.protocol_handling_client:main_null',
            'protocol_transfer = protocol_handler.protocol_transfer:main_null',
            'execute_command = zeroMQ_OT2.execute_command:main_null', 
            'external_server = zeroMQ_OT2.external_server:main_null',
            'ot2_client = zeroMQ_OT2.ot2_client:main_null',
            'OT2_listener = zeroMQ_OT2.OT2_listener:main_null',
        ],
    },
)
