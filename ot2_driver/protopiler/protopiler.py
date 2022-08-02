import copy
import json
import yaml
import argparse
from pathlib import Path
from itertools import repeat
from datetime import datetime
from typing import List, Optional, Tuple

from protopiler.config import PathLike, Command
from protopiler.resource_manager import ResourceManager


""" Things to do:
        [x] take in current resources, if empty default is full
        [x] allow partial tipracks, specify the tip location in the out protocol.py
        [x] resource manager as like a parasite class, just pass it around and update as needed
        [x] dispatch jobs?
        [v] (partially done, robot state in decent state) logging (both of state of robot and standard python logging) goal is to get to globus levels of logging
        [x] connect to opentrons and execute, should be outside this file, but since it doesn't exist, I am doing this now
        [ ] create smart templates, variable fields at the top that can be populated later
"""


class ProtoPiler:
    def __init__(
        self,
        config_path: Optional[PathLike] = None,
        template_dir: PathLike = Path("./protocol_templates"),
        resource_file: Optional[PathLike] = None,
    ) -> None:
        self.template_dir = template_dir
        self.resource_file = resource_file

        if self.resource_file:
            self.resource_file = Path(self.resource_file)

        self.config = None
        if config_path:
            self.load_config(config_path)

    def load_config(self, config_path: PathLike, resource_file: Optional[PathLike] = None) -> None:
        self.config_path = config_path
        self.resource_file = resource_file

        self.config = yaml.safe_load(open(config_path))
        self._parse_config()

    def _parse_config(self) -> None:
        """Create a programatic representation of ot2 protocol setup and execution
            provided by YAML

        Things we need:
            - Equipment: need location -> name and name -> location info?
                - pipettes installed
                - tipracks
                - wellplates
            - Commands
                - name: optional
                - source: str (may need wellplate name/location as well as cell location)
                - destination: str/[str]
                - volume: int/[int]



        Args:
            None: None

        Returns:
            None : None
        """
        # TODO: include more flexibility for file format. Types should allow for dict like assignments
        # as well as list like assignment
        # i.e i should be able to tell if a block is a labware/pipette vs a command block

        if isinstance(self.config, dict) and "equipment" in self.config and "commands" in self.config:
            # load metadata, optional
            self.metadata = self.config.get("metadata", None)

            self.resource_manager = ResourceManager(self.config["equipment"], resource_file=self.resource_file)

            # load the commands
            self.commands = [Command(**data) for data in self.config["commands"]]
            # post process on commands to accept alias:[str...] and [alias:loc] form
            self._postprocess_commands()

        else:
            raise Exception("Unknown configuration file format")

    def _postprocess_commands(self) -> None:  # Could use more testing
        """Processes the commands to support the alias syntax.


        In short, this method will accept commands of the sort:
            ```
              - name: example command
                source: source:[A1, A2, A3]
                destination: dest:[B1, B2, B3]
                volume: 100
            ```
        or:
            ```
              - name: example command
                source: [source:A1, alias:A2, source:A3]
                destination: [dest:B1, dest:B2, dest:B3]
                volume: 100
            ```
        You can also mix and match, provide a global alias outside the brackets and keep some of the aliases inside.
        The inside alias will always overrule the outside alias.
        """
        # TODO: do more testing of this function
        # TODO: can we make this better?
        for command in self.commands:
            if ":[" in command.source:
                new_locations = []
                alias = command.source.split(":")[0]
                process_source = copy.deepcopy(command.source)
                process_source = ":".join(process_source.split(":")[1:])  # split and rejoin after first colon
                process_source = process_source.strip("][").split(", ")

                for location in process_source:
                    if len(location) == 0:  # Handles list that end like this: ...A3, A4, ]
                        continue
                    new_location = None
                    if ":" not in location:
                        new_location = f"{alias}:{location}"
                        new_locations.append(new_location)
                    else:
                        new_locations.append(location)

                command.source = new_locations

            if ":[" in command.destination:
                new_locations = []
                alias = command.destination.split(":")[0]
                process_destination = copy.deepcopy(command.destination)
                process_destination = ":".join(
                    process_destination.split(":")[1:]
                )  # split and rejoin after first colon
                process_destination = process_destination.strip("][").split(", ")
                for location in process_destination:
                    if len(location) == 0:  # Handles list that end like this: ...A3, A4, ]
                        continue
                    new_location = None
                    if ":" not in location:
                        new_location = f"{alias}:{location}"
                        new_locations.append(new_location)
                    else:
                        new_locations.append(location)

                command.destination = new_locations

    def _reset(
        self,
    ) -> None:
        """Reset the class so that another config can be parsed without side effects


        TODO: this is messy, and seems to break the 'idea' of classes, think of how to avoid this
        """
        self.config = None
        self.metadata = None
        self.labware = None
        self.pipettes = None
        self.commands = None

        self.labware_to_location = None
        self.location_to_labware = None
        self.alias_to_location = None

        self.pipette_to_mount = None
        self.mount_to_pipette = None

    def yaml_to_protocol(
        self,
        config_path: Optional[PathLike] = None,
        protocol_out: PathLike = Path(f"./protocol_{datetime.now().strftime('%Y%m%d-%H%M%S')}.py"),
        resource_file: Optional[PathLike] = None,
        resource_file_out: Optional[PathLike] = None,
        write_resources: bool = True,
        overwrite_resources_json: bool = True,
        reset_when_done: bool = False,
    ) -> Tuple[Path]:
        """Public function that provides entrance to the protopiler. Creates the OT2 *.py file from a configuration

        Parameters
        ----------
        config_path : Optional[PathLike], optional
            Path to the config.yml file, by default None, can be passed to constructor
        protocol_out : PathLike, optional
            path to save the protocol file to, by default Path(f"./protocol_{datetime.now().strftime('%Y%m-%d%H-%M%S')}.py")
        resource_file : Optional[PathLike], optional
            If we are tracking resources, this is where the file will be saved, by default None and will mirror the protocol file naming
        resource_file_out : Optional[PathLike], optional
            If preset, the new resource file will be saved here
        reset_when_done : bool, optional
            reset the class variables when done, by default True
        """

        if not self.config:
            self.load_config(config_path)

        if protocol_out is None:
            protocol_out = Path(f"./protocol_{datetime.now().strftime('%Y%m%d-%H%M%S')}.py")

        protocol = []

        # Header and run() declaration with initial deck and pipette dicts
        header = open((self.template_dir / "header.template")).read()
        if self.metadata is not None:
            header = header.replace("#metadata#", f"metadata = {json.dumps(self.metadata, indent=4)}")
        else:
            header = header.replace("#metadata#", "")
        protocol.append(header)

        # load labware and pipette
        protocol.append("\n    ################\n    # load labware #\n    ################")

        labware_block = open((self.template_dir / "load_labware.template")).read()
        # TODO: think of some better software design for accessing members of resource manager
        for location, name in self.resource_manager.location_to_labware.items():
            labware_command = labware_block.replace("#name#", f'"{name}"')
            labware_command = labware_command.replace("#location#", f'"{location}"')

            protocol.append(labware_command)

        instrument_block = open((self.template_dir / "load_instrument.template")).read()

        # TODO: think of some better software design for accessing members of resource manager
        for mount, name in self.resource_manager.mount_to_pipette.items():
            pipette_command = instrument_block.replace("#name#", f'"{name}"')
            pipette_command = pipette_command.replace("#mount#", f'"{mount}"')

            # get valid tipracks
            valid_tiprack_locations = self.resource_manager.find_valid_tipracks(name)
            if len(valid_tiprack_locations) == 0:
                print(f"Warning, no tipracks found for: {name}")
            pipette_command = pipette_command.replace(
                "#tip_racks#",
                ", ".join([f'deck["{loc}"]' for loc in valid_tiprack_locations]),
            )
            protocol.append(pipette_command)

        # execute commands
        protocol.append("\n    ####################\n    # execute commands #\n    ####################")

        commands_python = self._create_commands()
        protocol.extend(commands_python)

        # TODO: anything to write for closing?

        with open(protocol_out, "w") as f:
            f.write("\n".join(protocol))

        # Hierarchy:
        # 1. resource out given
        # 2. resource file given, and writing resources is true
        # 3. self.resources is not none, we are writing resources, and can overwrite it if present
        # 4. we are writing resources but do not have either file, dump it here with generated name
        if resource_file_out is not None:
            resource_file_out = self.resource_manager.dump_resource_json(out_file=resource_file_out)

        elif resource_file and write_resources:
            resource_file_out = self.resource_manager.dump_resource_json(out_file=resource_file)

        elif self.resource_file and write_resources and overwrite_resources_json:
            resource_file_out = self.resource_manager.dump_resource_json(out_file=self.resource_file)

        elif write_resources:
            resource_file_out = self.resource_manager.dump_resource_json()

        if reset_when_done:
            self._reset()

        return protocol_out, resource_file_out

    def _create_commands(self) -> List[str]:
        """Creates the flow of commands for the OT2 to run

        Raises:
            Exception: If no tips are present for the current pipette
            Exception: If no wellplates are installed in the deck

        Returns:
            List[str]: python snippets of commands to be run
        """
        commands = []

        # load command templates
        aspirate_template = open((self.template_dir / "aspirate.template")).read()
        dispense_template = open((self.template_dir / "dispense.template")).read()
        pick_tip_template = open((self.template_dir / "pick_tip.template")).read()
        drop_tip_template = open((self.template_dir / "drop_tip.template")).read()

        tip_loaded = {"left": False, "right": False}
        for i, command_block in enumerate(self.commands):

            block_name = command_block.name if command_block.name is not None else f"command {i}"
            commands.append(f"\n    # {block_name}")
            for (volume, src, dst) in self._process_instruction(command_block):
                # determine which pipette to use
                pipette_mount = self.resource_manager.determine_pipette(volume)
                if pipette_mount is None:
                    raise Exception(f"No pipette available for {block_name} with volume: {volume}")

                # check for tip
                if not tip_loaded[pipette_mount]:
                    load_command = pick_tip_template.replace("#pipette#", f'pipettes["{pipette_mount}"]')
                    # TODO: think of some better software design for accessing members of resource manager
                    pipette_name = self.resource_manager.mount_to_pipette[pipette_mount]

                    # TODO: define flag to grab from specific well or just use the ones defined by the OT2
                    if True:
                        rack_location, well_location = self.resource_manager.get_next_tip(pipette_name)

                        location_string = f'deck["{rack_location}"].wells()[{well_location}]'
                        load_command = load_command.replace("#location#", location_string)
                    else:
                        load_command = load_command.replace("#location#", "")
                        self.resource_manager.update_tip_usage(pipette_name)

                    commands.append(load_command)
                    tip_loaded[pipette_mount] = True

                # aspirate and dispense
                src_wellplate_location = self._parse_wellplate_location(src)
                # should handle things not formed like loc:well
                src_well = src.split(":")[-1]

                aspirate_command = aspirate_template.replace("#pipette#", f'pipettes["{pipette_mount}"]')
                aspirate_command = aspirate_command.replace("#volume#", str(volume))
                aspirate_command = aspirate_command.replace(
                    "#src#", f'deck["{src_wellplate_location}"]["{src_well}"]'
                )
                commands.append(aspirate_command)
                # update resource usage
                self.resource_manager.update_well_usage(src_wellplate_location, src_well)

                dst_wellplate_location = self._parse_wellplate_location(dst)
                dst_well = dst.split(":")[-1]  # should handle things not formed like loc:well
                dispense_command = dispense_template.replace("#pipette#", f'pipettes["{pipette_mount}"]')
                dispense_command = dispense_command.replace("#volume#", str(volume))
                dispense_command = dispense_command.replace(
                    "#dst#", f'deck["{dst_wellplate_location}"]["{dst_well}"]'
                )
                commands.append(dispense_command)
                # update resource usage
                self.resource_manager.update_well_usage(dst_wellplate_location, dst_well)

                if command_block.drop_tip:
                    drop_command = drop_tip_template.replace("#pipette#", f'pipettes["{pipette_mount}"]')
                    commands.append(drop_command)
                    tip_loaded[pipette_mount] = False

                commands.append("")

        for mount, status in tip_loaded.items():
            if status:
                commands.append(drop_tip_template.replace("#pipette#", f'pipettes["{mount}"]'))
                tip_loaded[mount] = False

        return commands

    def _parse_wellplate_location(self, command_location: str) -> str:
        """Finds the correct wellplate give the commands location

        Parameters
        ----------
        command_location : str
            The raw command coming from the input file. Form: `alias:Well` or `Well`. Function accepts both

        Returns
        -------
        str
            The wellplate location in string form (will be in range 1-9, due to ot2 deck size)

        Raises
        ------
        Exception
            If the command is not formatted correctly, it should get caught before this, but if not I check here
        """
        location = None
        if ":" in command_location:  # new format, pass a wellplate location, then well location
            try:
                plate, _ = command_location.split(":")
            except ValueError:
                raise Exception(f"Command: {command_location} is not formatted correctly...")

            # TODO: think of some better software design for accessing members of resource manager
            location = self.resource_manager.alias_to_location[plate]
        else:  # older format of passing location
            for name, loc in self.labware_to_location.items():
                if "well" in name:
                    if location is not None:
                        print(f"Location {location} is overwritten with {loc}, multiple wellplates present")
                    if type(loc) is list and len(loc) > 1:
                        print(
                            f"Ambiguous command '{command_location}', multiple plates satisfying params (locations: {loc}) found, choosing location: {loc[0]}..."
                        )
                        location = loc[0]
                    elif type(loc) is list and len(loc) == 1:
                        location = loc[0]
                    elif type(loc) is str:
                        location = loc

        return location

    def _process_instruction(self, command_block: Command) -> List[str]:
        """Processes a command block to translate into the protocol information.

        Supports unrolling over any dimension, syntactic sugar at best, but might come in handy someday

        Parameters
        ----------
        command_block : Command
            The command dataclass parsed directly from the file. See the `example_configs/` directory for examples.

        Returns
        -------
        List[str]
            Yields a triple of [volume, source, destination] values until there are no values left to be consumed

        Raises
        ------
        Exception
            If the command is not formatted correctly and there are different dimension iterables present, exception is raised.
            This function either supports one field being an iterable with length >1, or they all must be iterables with the same length.
        """
        if (
            type(command_block.volume) is int
            and type(command_block.source) is str
            and type(command_block.destination) is str
        ):

            yield command_block.volume, command_block.source, command_block.destination
        else:
            # could be one source (either list of volumes or one volume) to many desitnation
            # could be many sources (either list of volumes or one volume) to one destination
            # could be one source/destination, many volumes

            # TODO: think about optimizatoins. e.g if you are dispensing from one well to multiple
            # destinations, we could pick up the sum of the volumes and drop into each well without
            # the whole dispense, drop tip, pick up tip, aspirate in the middle

            # since we are here we know at least one of the things is a list
            iter_len = 0
            if isinstance(command_block.volume, list):
                # handle if user forgot to change list of one value to scalar
                if len(command_block.volume) == 1:
                    command_block.volume = command_block.volume[0]
                else:
                    iter_len = len(command_block.volume)
            if isinstance(command_block.source, list):
                if iter_len != 0 and len(command_block.source) != iter_len:
                    # handle if user forgot to change list of one value to scalar
                    if len(command_block.source) == 1:
                        command_block.source = command_block.source[0]
                    else:
                        raise Exception("Multiple iterables found, cannot deterine dimension to iterate over")
                iter_len = len(command_block.source)
            if isinstance(command_block.destination, list):
                if iter_len != 0 and len(command_block.destination) != iter_len:
                    # handle if user forgot to change list of one value to scalar
                    if len(command_block.destination) == 1:
                        command_block.destination = command_block.destination[0]
                    else:
                        raise Exception(
                            "Multiple iterables of differnet lengths found, cannot deterine dimension to iterate over"
                        )
                iter_len = len(command_block.destination)

            if not isinstance(command_block.volume, list):
                volumes = repeat(command_block.volume, iter_len)
            else:
                volumes = command_block.volume
            if not isinstance(command_block.source, list):
                sources = repeat(command_block.source, iter_len)
            else:
                sources = command_block.source
            if not isinstance(command_block.destination, list):
                destinations = repeat(command_block.destination, iter_len)
            else:
                destinations = command_block.destination

            for vol, src, dst in zip(volumes, sources, destinations):
                yield vol, src, dst


def main(config_path):
    # TODO: Think about how a user would want to interact with this, do they want to interact with something like a
    # SeqIO from Biopython? Or more like a interpreter kind of thing? That will guide some of this... not sure where
    # its going right now
    ppiler = ProtoPiler()

    ppiler.yaml_to_protocol(
        config_path=config_path,
        out_file="./test_protocol.py",
        resource_file="./test_resources.json",
        reset_when_done=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", help="YAML config file", type=str, required=True)
    args = parser.parse_args()
    main(args.config)
