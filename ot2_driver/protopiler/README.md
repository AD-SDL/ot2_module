# Protopiler

Sub module of the OT2 driver that allows for configuration style creation of protocols. 

### Command line arguments: 
```
usage: protopiler.py [-h] -c CONFIG [-po PROTOCOL_OUT] [-ro RESOURCE_OUT] [-ri RESOURCE_IN]

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        YAML config file
  -po PROTOCOL_OUT, --protocol_out PROTOCOL_OUT
                        Path to save the protocol to
  -ri RESOURCE_IN, --resource_in RESOURCE_IN
                        Path to existing resource file to update
  -ro RESOURCE_OUT, --resource_out RESOURCE_OUT
                        Path to save the resource file to

```

### Running with basic configurations 
To run with the basic configuration found in `ot2_driver/protopiler/test_configs/basic_config.yaml`, run the following 

```
python protopiler.py -c test_configs/basic_config.yaml -po [path/to/protocol/out] -ri [path/to/existing/resource/file] -ro [path/to/resource/out/file]
```

# Deconstructor \**beta*\*

There is currently a *very* rough implementation of a deconstructor program that takes a protocol.py file and turns it into a config.yml 

For now I have only tested with protocols I have written but I have no reason to beleive it wouldnt work with them. This requires a lot more testing, though. 

### Command line args

```
usage: deconstructor.py [-h] -p PROTOCOL [-co CONFIG_OUT] [-os OPENTRONS_SIMULATE]

optional arguments:
  -h, --help            show this help message and exit
  -p PROTOCOL, --protocol PROTOCOL
                        Path to the input protocol
  -co CONFIG_OUT, --config_out CONFIG_OUT
                        Path to output config file
  -os OPENTRONS_SIMULATE, --opentrons_simulate OPENTRONS_SIMULATE
                        Path to the opentrons simulate program, optional

```

To run on the basic_config.py: 
```
python deconstructor.py -p test_configs/basic_config.py -co [path/to/config/out]
```