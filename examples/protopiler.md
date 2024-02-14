# Protopiler example usage

## Simple protocol

A protopiler config consists of three things, `equipment`, `commands`, `metadata`.

Below is an example of the most basic configuration we can create:
```yaml
equipment:
  - name: corning_96_wellplate_360ul_flat
    location: "2"
    alias: source
  - name: corning_96_wellplate_360ul_flat
    location: "3"
    alias: dest
  - name: opentrons_96_tiprack_1000ul
    location: "8"
  - name: p1000_single_gen2
    mount: right
commands:
  - name: example command
    source: source:A1
    destination: dest:A1
    volume: 100
  - name: other command
    source: source:A2
    destination: dest:A2
    volume: 100
metadata:
  protocolName: Example Name
  author: Kyle khippe@anl.gov
  description: some detailed description
  apiLevel: "2.12"

```

In the `equipment` portion of the config, we specify two wellplates (one with a `source` alias and another with a `destination` alias, you can make whatever name you would like for the alias), one tiprack, and one pipette. Make sure the name of the equipment object is the opentrons name for them.

Next in the commands, we have two commands, transferring `100ul` of liquid from the source plate at `A1` to the destination plate at `A1`, and the same procedure for `A2` of both plates.

Lastly we have the metadata, this is optional but recommended. It should contain the `protocolName`, `author`, `description`, and `apiLevel` (as of 8/8/2022 this should be `"2.12"`)

To compile this into a protocol run the following command:
```
python ot2_driver/protopiler/protopiler.py -c  ot2_driver/protopiler/test_configs/basic_config.yaml -po ./test_protocol.py -ro ./test_resources.json
```

If you have an existing resource file that you would like to update instead, run this command:
```
python ot2_driver/protopiler/protopiler.py -c  ot2_driver/protopiler/test_configs/basic_config.yaml -po ./test_protocol.py -ri ./test_resources.json -ro ./test_resources_new.json
```


## More advanced examples

### Lists of actions in commands

*The `equipment` and `metadata` are the same as the last example*

I have provided a syntax for simplifying repetitive commands.

```yaml
commands:
  - name: example command
    source: source:[A1, A2, A3]
    destination: source:[B1, B2, B3]
    volume: [15, 100, 700]
```

This command is interpreted as transferring `15ul` from `A1 -> B1` in the source plate, `100ul` from `A2 -> B2` in the source plate, and `700ul` from `A3 -> B3` in the source wellplate.

If you would like to transfer from arbitrary plates inside a list, you can pull the location alias to inside in front of specific elements:


```yaml
commands:
  - name: example command
    source: [source:A1, destination:A2, source:A3]
    destination: destination:[B1, B2, B3]
    volume: [15, 100, 700]
```

This command transfers `15ul` from the `A1` in the source to `B1` in the destination location, then `100ul` from `A2 -> B2` in the destination plate, then `700ul` from `A3` in the source location to `B3` in the destination location

### Dimension Unwrapping

Say you have a single source well but multiple destinations, you can use this syntax to do this easier than writing the source well over and over:

```yaml
commands:
  - name: example command
    source: source:A1
    destination: destination:[B1, B2, B3]
    volume: [15, 100, 700]
```

This will first transfer `15ul` from `A1` in the source location to `B1` in the destination, then `100ul` to `B2`, and `700ul` to `B3` in the destination.

You can have any combination of all three keys (`source`, `destination`, `volume`) as lists. If there are two or more lists present, they must be the same length, otherwise the single list will determine the number of transfers in this command.

Below are more examples of this:

```yaml
commands:
  - name: example command
    source: source:[A1, A2, A3]
    destination: destination:[B1, B2, B3]
    volume: 75
```
This transfers 75ul from A1 of source to B1 of destination location, and so on for the remaining locations.
