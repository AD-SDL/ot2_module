### Installation 
1. `git clone https://github.com/KPHippe/ot2_driver.git`
2. Switch to my dev branch `git checkout dev-kyle`
3. I would recommend a conda/venv environment. The following assusumes conda. 
    1. `conda create -n ot2-driver python=3.9`
    1. `conda activate ot2-driver`
    1. `pip install -r requirements.txt` 
    1. `pip install -e .`
    
*This installs ot2_driver as a package*

### Getting the OT2 setup for ssh
*This is not required (or used) for the HTTP driver* 
When setting up an ssh key to connect to the opentrons, it is helpful to make a new one without a passphrase. For more information on setting up an ssh connection see:

*Note, you have to have the Opentrons App installed*

- https://support.opentrons.com/en/articles/3203681-setting-up-ssh-access-to-your-ot-2
- https://support.opentrons.com/en/articles/3287453-connecting-to-your-ot-2-with-ssh

For prototyping in the RPL, connect via the wire and wait for the robot to become visible on the application. Click `settings` then `network settings` and if you intend on running via the wire, use the `wired-ip` in the robot configuration file. If you intend to use the wireless IP, you must connect to the `snowcrash` network, but this does not have internet access. 

### Robot config 

Below is an example of what I refer to as the `robot_config` 
```
# OT2 in lab
- ip: IP.ADDRESS
  ssh_key: full/path/to/ssh/key # optional of http, just have a dummy string for now
  model: OT2
  version: 5 # If unsure, leave at 5

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

To run your own protocol.py file, replace data in the `-pc` option with the path to your protocol.py file
```
python ot2_driver_ssh.py -rc [insert/robot/config/path] -pc ./test_protocol.py
```

*The process is the same for the HTTP driver* 

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
### Updating the Code on node computer
1.  `cd ~/wei_ws/src/ot2_driver`
2.  `git pull`
3.  `pip install -e .`
### Running Dev Tools 
 
1. Install `pip install -r requirements/dev.txt`
2. Run `make` in project root
