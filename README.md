# OT2 abstraction requirments
Moving OT2 abstractions out of ROS network. 

## Naming Conventions
Package **must** be named `ot2_driver_pkg`, and file must be named `ot2_driver`. **No other package** will be imported into the ROS network, and thus invisible to the ROS layer.  

Packages **must** follow ROS 2 python package format, see useful commands below! (Note, the way you link internal packges **must** also follow ROS 2 package formats)

## Functions needed 
* load_protocol(protocol_path, robot_id)
    * Loads the protocol to the ot2_driver (knows what protocol code is, current driver does this via database)
    * Inserts in error handling into the protocol
* run_protocol(protocol_id, username, ip, port)
    * Runs the given protocol id on the specified internal RPI4
    * TODO: get that internal RPI4 specifications from config file not passed via arguments

## Useful ROS Commands
* `ros2 pkg create --build-type ament_python <package_name>` Creates the barebones for a new ROS 2 package
* `colcon graph --dot | dot -Tpng -o deps.png` Generates a dependency graph

## Installation Instructions
1. `git clone https://github.com/AD-SDL/ot2_driver_pkg.git`

## Instructions for Kyle's driver 

### Installation 
1. `git clone https://github.com/KPHippe/ot2_driver.git`
1. I would recommend a conda/venv environment. The following assusumes conda. 
    1. `conda create -n ot2-driver python=3.9`
    1. `conda activate ot2-driver`
    1. `pip install -r requirements.txt` 

### Getting the OT2 setup for ssh 
When setting up an ssh key to connect to the opentrons, it is helpful to make a new one without a passphrase. For more information on setting up an ssh connection see:

*Note, you have to have the Opentrons App installed*

- https://support.opentrons.com/en/articles/3203681-setting-up-ssh-access-to-your-ot-2
- https://support.opentrons.com/en/articles/3287453-connecting-to-your-ot-2-with-ssh

For prototyping in the RPL, connect via the wire and wait for the robot to become visible on the application. Click `settings` then `network settings` and if you intend on running via the wire, use the `wired-ip` in the robot configuration file. If you intend to use the wireless IP, you must connect to the `snowcrash` network, but this does not have internet access. 

### Robot config 

Below is an example of what i refer to as the `robot_config` 
```
# OT2 in lab
- ip: IP.ADDRESS
  ssh_key: full/path/to/ssh/key 
  model: OT2
  version: 5 # If insure, leave at 5

```

### Running the driver 

If you would like to use the script as I have made it, I have provided command line descriptions and example commands below

```
usage: ot2_driver_ssh.py [-h] -rc ROBOT_CONFIG [-pc PROTOCOL_CONFIG] [-rf RESOURCE_FILE] [-s] [-d] [-v] [-po PROTOCOL_OUT] [-ro RESOURCE_OUT]

optional arguments:
  -h, --help            show this help message and exit
  -rc ROBOT_CONFIG, --robot_config ROBOT_CONFIG
                        Path to config for OT2(s), must be present even if simulating, can contain dummy data however
  -pc PROTOCOL_CONFIG, --protocol_config PROTOCOL_CONFIG
                        Path to protocol config or protocol.py
  -rf RESOURCE_FILE, --resource_file RESOURCE_FILE
                        Path to resource file that currently exists
  -po PROTOCOL_OUT, --protocol_out PROTOCOL_OUT
                        Optional, name/location for protocol file to be saved to
  -ro RESOURCE_OUT, --resource_out RESOURCE_OUT
                        Optional, name/location for resources used file to be saved to
  -s, --simulate        Simulate the run, don't actually connect to the opentrons
  -d, --delete          Delete resource files and protocol files when done, default false
  -v, --verbose         Print status along the way

```

To run the `protopiler/example_configs/basic_config.yaml` with verbose settings and default outs, run the following 
```
python ot2_driver_ssh.py -rc [insert/robot/config/path] -pc protopiler/example_configs/basic_config.yaml -v
```
To run the `protopiler/example_configs/basic_config.yaml` with verbose settings and specify the output files, run the following 

```
python ot2_driver_ssh.py -rc [insert/robot/config/path] -pc protopiler/example_configs/basic_config.yaml -po ./test_protocol.py -ro ./test_resources.json -v 
```

To run your own protocol.py file, replace the `-pc` option with the path to your protocol.py file
```
python ot2_driver_ssh.py -rc [insert/robot/config/path] -pc ./test_protocol.py
```


If you would like to write your own code using the ot2 driver you can start with something like this
```python
# would have to specify path to ot2_driver_ssh.py if not in directory
from ot2_driver_ssh import OT2_Driver 

# Load one ot2
for ot2_raw_cfg in yaml.safe_load(open(`robot_config_path`)):
    ot2 =OT2_Driver(OT2_Config(**ot2_raw_cfg))

# if you need to compile the protocol from yaml
if "py" not in str(`protocol_config`):

    protocol_file, resource_file = ot2.compile_protocol(
        config_path=`protocol_config`,
        resource_file=`resource_file`,
        protocol_out=`protocol_out`,
        resource_out=`resource_out`,
    )
    

# Transfer the protocol to the ot2 
transfer_returncode = ot2.transfer(protocol_file)
if returncode:
    print("Exception raised when transferring...")

# Execute the protocol 
ot2.execute(protocol_file)

```