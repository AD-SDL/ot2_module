# Using OT2 driver

If you would like to use the script as I have made it, I have provided command line descriptions and example commands below

```
usage: ot2_driver_ssh.py [-h] -rc ROBOT_CONFIG [-pc PROTOCOL_CONFIG] [-rf RESOURCE_FILE] [-po PROTOCOL_OUT] [-ro RESOURCE_OUT] [-s] [-d] [-v]

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

To run the `protopiler/test_configs/basic_config.yaml` with verbose settings and default outs, run the following 
```
python ot2_driver_ssh.py -rc [insert/robot/config/path] -pc protopiler/test_configs/basic_config.yaml -v
```
To run the `protopiler/test_configs/basic_config.yaml` with verbose settings and specify the output files, run the following 

```
python ot2_driver_ssh.py -rc [insert/robot/config/path] -pc protopiler/test_configs/basic_config.yaml -po ./test_protocol.py -ro ./test_resources.json -v 
```

To run your own protocol.py file, replace data in the `-pc` option with the path to your protocol.py file
```
python ot2_driver_ssh.py -rc [insert/robot/config/path] -pc ./test_protocol.py
```

*The process is the same for the HTTP driver* 

If you would like to write your own code using the ot2 driver you can start with something like this
```python
from ot2_driver.ot2_driver_ssh import OT2_Driver 

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

To use the HTTP version, this would be an example script: 
```python
from ot2_driver.ot2_driver_http import OT2_Driver 

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
protocol_id, run_id = ot2.transfer(protocol_file)

# Execute the protocol 
ot2.execute(run_id)
```