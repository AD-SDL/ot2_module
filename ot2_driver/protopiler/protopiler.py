import re
import copy
import json
import yaml
import argparse
from pathlib import Path
from itertools import repeat
from datetime import datetime
from typing import List, Optional, TypeVar, Union, Dict, Type

from pydantic import BaseSettings as _BaseSettings


""" Things to do:
        [ ] take in current resources, if empty default is full
        [ ] allow partial tipracks, specify the tip location in the out protocol.py
        [ ] resource manager as like a parasite class, just pass it around and update as needed
        [ ] dispatch jobs?
        [ ] logging (both of state of robot and standard python logging) goal is to get to globus levels of logging
        [ ] connect to opentrons and execute, should be outside this file, but since it doesn't exist, I am doing this now
        [ ] create smart templates, variable fields at the top that can be populated later
"""

_T = TypeVar("_T")

PathLike = Union[str, Path]


class BaseSettings(_BaseSettings):
    def dump_yaml(self, cfg_path: PathLike) -> None:
        with open(cfg_path, mode="w") as fp:
            yaml.dump(json.loads(self.json()), fp, indent=4, sort_keys=False)

    @classmethod
    def from_yaml(cls: Type[_T], filename: PathLike) -> _T:
        with open(filename) as fp:
            raw_data = yaml.safe_load(fp)
        return cls(**raw_data)  # type: ignore[call-arg]

    @classmethod
    def from_bytes(cls: Type[_T], raw_bytes: bytes) -> _T:
        raw_data = yaml.safe_load(raw_bytes)
        return cls(**raw_data)  # type: ignore[call-arg]


_T = TypeVar("_T")

PathLike = Union[Path, str]

# Labware containers
class Labware(BaseSettings):
    name: str
    location: str
    alias: Optional[str]


class Pipette(BaseSettings):
    name: str
    mount: str


# Command container
class Command(BaseSettings):
    name: Optional[str]
    source: Union[List[str], str]
    destination: Union[str, List[str]]
    volume: Union[int, List[int]]
    drop_tip: bool = True


# metadata container
class Metadata(BaseSettings):
    protocolName: Optional[str]
    author: Optional[str]
    description: Optional[str]
    apiLevel: Optional[str] = "2.12"


class ProtoPiler:
    def __init__(
        self,
        config_path: Optional[PathLike] = None,
        template_dir: PathLike = Path("./protocol_templates"),
        resource_tracking: bool = False,
    ) -> None:
        self.template_dir = template_dir
        self.resource_tracking = resource_tracking

        self.config = None
        if config_path:
            self.load_config(config_path)

    def load_config(self, config_path: PathLike) -> None:
        self.config_path = config_path
        self.config = yaml.safe_load(open(config_path))
        self._parse_config()

    def _parse_config(
        self,
    ) -> None:
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
        self.labware = []
        self.pipettes = []

        # TODO: include more flexibility for file format. Types should allow for dict like assignments
        # as well as list like assignment
        # i.e i should be able to tell if a block is a labware/pipette vs a command block

        if (
            isinstance(self.config, dict)
            and "equipment" in self.config
            and "commands" in self.config
        ):
            # load metadata, optional
            self.metadata = self.config.get("metadata", None)

            # load the labware
            # TODO: split this into a method like process commands?
            for data in self.config["equipment"]:
                if (
                    isinstance(data, dict) and len(data) == 1
                ):  # it is in form {"name": {'info': info }}
                    for _name, elem_data in data.items():
                        if "location" in elem_data.keys():
                            self.labware.append(Labware(**elem_data))
                        elif "mount" in elem_data.keys():
                            self.pipettes.append(Pipette(**elem_data))
                else:  # in form {"info": info}
                    if "location" in data.keys():
                        self.labware.append(Labware(**data))
                    elif "mount" in data.keys():
                        self.pipettes.append(Pipette(**data))

            # load the commands
            self.commands = [Command(**data) for data in self.config["commands"]]
            # post process on commands to accept alias:[str...] and [alias:loc] form
            self._postprocess_commands()

        else:
            raise Exception("Unknown configuration file format")

        if len(self.labware) == 0:
            raise Exception("No labware present in config")
        if len(self.pipettes) == 0:
            raise Exception("No pippetes present")

        # generate name -> location and location -> name relationships for labware
        self.labware_to_location = {}
        self.location_to_labware = {}
        self.alias_to_location = {}

        self.pipette_to_mount = {}
        self.mount_to_pipette = {}

        # generate labware -> location and location -> labware association
        for element in self.labware:
            if element.name in self.labware_to_location:
                self.labware_to_location[element.name].append(element.location)
            else:
                self.labware_to_location[element.name] = [element.location]

            if element.location in self.location_to_labware:
                raise Exception(
                    "Labware location overloaded, please check configuration"
                )
            self.location_to_labware[element.location] = element.name

            if element.alias:
                self.alias_to_location[element.alias] = element.location

            # adding both the alias and the location just in case the user uses it interchangeably
            self.alias_to_location[element.location] = element.location

        for element in self.pipettes:
            # Generate pipette -> mount association
            if element.mount in self.mount_to_pipette:
                raise Exception(
                    "Pipette location overloaded, please check configuration"
                )

            self.mount_to_pipette[element.mount] = element.name

            if element.name in self.pipette_to_mount:
                self.pipette_to_mount[element.name].append(element.mount)
            else:
                self.pipette_to_mount[element.name] = [element.mount]

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
        for command in self.commands:
            if ":[" in command.source:
                new_locations = []
                alias = command.source.split(":")[0]
                process_source = copy.deepcopy(command.source)
                process_source = ":".join(
                    process_source.split(":")[1:]
                )  # split and rejoin after first colon
                process_source = process_source.strip("][").split(", ")

                for location in process_source:
                    if (
                        len(location) == 0
                    ):  # Handles list that end like this: ...A3, A4, ]
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
                    if (
                        len(location) == 0
                    ):  # Handles list that end like this: ...A3, A4, ]
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
        out_file: PathLike = Path(
            f"./protocol_{datetime.now().strftime('%Y%m%d-%H%M%S')}.py"
        ),
        resource_file: Optional[PathLike] = None,
        resource_tracking: bool = True,
        reset_when_done: bool = True,
    ) -> Path:
        """Public function that provides entrance to the protopiler. Creates the OT2 *.py file from a configuration

        Parameters
        ----------
        config_path : Optional[PathLike], optional
            Path to the config.yml file, by default None, can be passed to constructor
        out_file : PathLike, optional
            path to save the protocol file to, by default Path(f"./protocol_{datetime.now().strftime('%Y%m-%d%H-%M%S')}.py")
        resource_file : Optional[PathLike], optional
            If we are tracking resources, this is where the file will be saved, by default None and will mirror the protocol file naming
        reset_when_done : bool, optional
            reset the class variables when done, by default True
        """

        if not self.config:
            self.load_config(config_path)

        if self.resource_tracking != resource_tracking:
            track_this_config = resource_tracking
        else:
            track_this_config = self.resource_tracking

        protocol = []
        resource_tracker = None
        if track_this_config:
            resource_tracker = {}
            self._setup_tracker(resource_tracker)

        # Header and run() declaration with initial deck and pipette dicts
        header = open((self.template_dir / "header.template")).read()
        if self.metadata is not None:
            header = header.replace(
                "#metadata#", f"metadata = {json.dumps(self.metadata, indent=4)}"
            )
        else:
            header = header.replace("#metadata#", "")
        protocol.append(header)

        # load labware and pipette
        protocol.append(
            "\n    ################\n    # load labware #\n    ################"
        )

        labware_block = open((self.template_dir / "load_labware.template")).read()
        for location, name in self.location_to_labware.items():
            labware_command = labware_block.replace("#name#", f'"{name}"')
            labware_command = labware_command.replace("#location#", f'"{location}"')

            protocol.append(labware_command)

        instrument_block = open((self.template_dir / "load_instrument.template")).read()

        for mount, name in self.mount_to_pipette.items():
            pipette_command = instrument_block.replace("#name#", f'"{name}"')
            pipette_command = pipette_command.replace("#mount#", f'"{mount}"')

            # get valid tipracks
            valid_tiprack_locations = self._find_valid_tipracks(name)
            if len(valid_tiprack_locations) == 0:
                print(f"Warning, no tipracks found for: {name}")
            pipette_command = pipette_command.replace(
                "#tip_racks#",
                ", ".join([f'deck["{loc}"]' for loc in valid_tiprack_locations]),
            )
            protocol.append(pipette_command)

        # execute commands
        protocol.append(
            "\n    ####################\n    # execute commands #\n    ####################"
        )

        commands_python = self._create_commands(resource_tracker)
        protocol.extend(commands_python)

        # TODO: anything to write for closing?

        with open(out_file, "w") as f:
            f.write("\n".join(protocol))

        if track_this_config:
            # prune the set datatype, we shouldn't need it
            for location in resource_tracker.keys():
                resource_tracker[location].pop(
                    "wells_used", None
                )  # returns none if DNE
            if not resource_file:
                name = f"{out_file.stem}_resources.json"
                resource_file = Path(out_file).parent / name

            with open(resource_file, "w") as f:
                json.dump(resource_tracker, f, indent=2)

        if reset_when_done:
            self._reset()

        return out_file

    def _setup_tracker(self, resource_tracker: dict) -> None:
        """Things to track:

        - pipette tips used
        - wells used
        - quantities of liquids used?

        Parameters
        ----------
        resource_tracker : dict
            dictionary setup with keys/vals to track resource usage of a config/protocol
        """

        for name, location in self.labware_to_location.items():
            if isinstance(location, list):
                for loc in location:
                    resource_tracker[loc] = {"name": name, "used": 0, "depleted": False}
                    if "wellplate" in name:  # adding the wellplate set tracker
                        resource_tracker[loc]["wells_used"] = set()
            else:
                resource_tracker[location] = {
                    "name": name,
                    "used": 0,
                    "depleted": False,
                }
                if "wellplate" in name:  # adding the wellplate set tracker
                    resource_tracker[location]["wells_used"] = set()

    def _find_valid_tipracks(self, pipette_name: str) -> List[str]:
        """Finds the valid tipracks for a given pipette

        TODO: If we end up with custom labware, either make sure it follows the opentrons naming scheme, or change this function.

        Parameters
        ----------
        pipette_name : str
            the opentrons API name for the pipette. Contains the volume of the pipette

        Returns
        -------
        List[str]
            A list of string integers representing the location of the valid tipracks on the deck `['1', '2', ... ]`

        """

        pip_volume_pattern = re.compile(r"p\d{2,}")
        rack_volume_pattern = re.compile(r"\d{2,}ul$")
        # find suitable tipracks
        pip_volume = int(
            pip_volume_pattern.search(pipette_name).group().replace("p", "")
        )
        valid_tipracks = []
        for labware_name, locations in self.labware_to_location.items():
            matches = rack_volume_pattern.search(labware_name)
            if matches is not None:
                vol = int(matches.group().replace("ul", ""))
                if vol == pip_volume:
                    for location in locations:
                        valid_tipracks.append(str(location))

        return valid_tipracks

    def _create_commands(self, resource_tracker: Optional[dict] = None) -> List[str]:
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

            block_name = (
                command_block.name if command_block.name is not None else f"command {i}"
            )
            commands.append(f"\n    # {block_name}")
            for (volume, src, dst) in self._process_instruction(command_block):
                # determine which pipette to use
                pipette_mount = self._determine_instrument(volume)
                if pipette_mount is None:
                    raise Exception(
                        f"No pipette available for {block_name} with volume: {volume}"
                    )

                # check for tip
                if not tip_loaded[pipette_mount]:
                    load_command = pick_tip_template.replace(
                        "#pipette#", f'pipettes["{pipette_mount}"]'
                    )
                    commands.append(load_command)
                    tip_loaded[pipette_mount] = True
                    if resource_tracker:
                        # TODO: need to figure out which tiprack it is pulling from. How does OT2 handle multiple tipracks
                        # For now assume its in the order its stored in the dict (i know it shouldnt be constant, but in python3.8 it is...)
                        pipette_name = self.mount_to_pipette[pipette_mount]
                        tiprack_locations = self._find_valid_tipracks(pipette_name)
                        updated_tiprack_usage = False
                        for rack_location in tiprack_locations:
                            rack_capacity = int(
                                self.location_to_labware[rack_location].split("_")[1]
                            )  # TODO: highly dependent on opentrons naming
                            if resource_tracker[rack_location]["used"] >= rack_capacity:
                                resource_tracker[rack_location]["depleted"] = True
                                continue

                            resource_tracker[rack_location]["used"] += 1
                            updated_tiprack_usage = True

                            # check if that was the last tip
                            if resource_tracker[rack_location]["used"] >= rack_capacity:
                                resource_tracker[rack_location]["depleted"] = True

                            break  # just need the first one that has space

                        if not updated_tiprack_usage:  # we know we ran out of tips
                            raise Exception(
                                "No more tips, protocol does not have enough resources..."
                            )

                # aspirate and dispense
                src_wellplate_location = self._find_wellplate(src)
                src_well = src.split(":")[
                    -1
                ]  # should handle things not formed like loc:well

                aspirate_command = aspirate_template.replace(
                    "#pipette#", f'pipettes["{pipette_mount}"]'
                )
                aspirate_command = aspirate_command.replace("#volume#", str(volume))
                aspirate_command = aspirate_command.replace(
                    "#src#", f'deck["{src_wellplate_location}"]["{src_well}"]'
                )
                commands.append(aspirate_command)
                # update resources if exist
                if resource_tracker:
                    resource_tracker[src_wellplate_location]["wells_used"].add(src_well)
                    resource_tracker[src_wellplate_location]["used"] = len(
                        resource_tracker[src_wellplate_location]["wells_used"]
                    )

                dst_wellplate_location = self._find_wellplate(dst)
                dst_well = dst.split(":")[
                    -1
                ]  # should handle things not formed like loc:well
                dispense_command = dispense_template.replace(
                    "#pipette#", f'pipettes["{pipette_mount}"]'
                )
                dispense_command = dispense_command.replace("#volume#", str(volume))
                dispense_command = dispense_command.replace(
                    "#dst#", f'deck["{dst_wellplate_location}"]["{dst_well}"]'
                )
                commands.append(dispense_command)
                # update resources if exist
                if resource_tracker:
                    resource_tracker[dst_wellplate_location]["wells_used"].add(dst_well)
                    resource_tracker[dst_wellplate_location]["used"] = len(
                        resource_tracker[dst_wellplate_location]["wells_used"]
                    )

                if command_block.drop_tip:
                    drop_command = drop_tip_template.replace(
                        "#pipette#", f'pipettes["{pipette_mount}"]'
                    )
                    commands.append(drop_command)
                    tip_loaded[pipette_mount] = False

                commands.append("")

        for mount, status in tip_loaded.items():
            if status:
                commands.append(
                    drop_tip_template.replace("#pipette#", f'pipettes["{mount}"]')
                )
                tip_loaded[mount] = False

        return commands

    def _determine_instrument(self, target_volume: int) -> str:
        """Determines which pippette to use for a given volume

        Parameters
        ----------
        target_volume : int
            The volume (in microliters) to be aspirated

        Returns
        -------
        str
            The location (in string form) of the pipette we are going to use. Either `right` or `left`
        """
        pipette = None
        min_available = float("inf")
        pip_volume_pattern = re.compile(r"\d{2,}")
        for mount, name in self.mount_to_pipette.items():

            pip_volume = int(pip_volume_pattern.search(name).group())

            if pip_volume >= target_volume:
                if pip_volume < min_available:
                    min_available = pip_volume
                    pipette = mount

        return pipette

    def _find_wellplate(self, command_location: str) -> str:
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
        if (
            ":" in command_location
        ):  # new format, pass a wellplate location, then well location
            try:
                plate, _ = command_location.split(":")
            except ValueError:
                raise Exception(
                    f"Command: {command_location} is not formatted correctly..."
                )

            location = self.alias_to_location[plate]
        else:  # older format of passing location
            for name, loc in self.labware_to_location.items():
                if "well" in name:
                    if location is not None:
                        print(
                            f"Location {location} is overwritten with {loc}, multiple wellplates present"
                        )
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
                # handle if forgot to change list of one value to scalar
                if len(command_block.volume) == 1:
                    command_block.volume = command_block.volume[0]
                else:
                    iter_len = len(command_block.volume)
            if isinstance(command_block.source, list):
                if iter_len != 0 and len(command_block.source) != iter_len:
                    # handle if forgot to change list of one value to scalar
                    if len(command_block.source) == 1:
                        command_block.source = command_block.source[0]
                    else:
                        raise Exception(
                            "Multiple iterables found, cannot deterine dimension to iterate over"
                        )
                iter_len = len(command_block.source)
            if isinstance(command_block.destination, list):
                if iter_len != 0 and len(command_block.destination) != iter_len:
                    # handle if forgot to change list of one value to scalar
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

    """
    Everything under here is for getting a config from an existing protocol, currently a work in progress...
    """

    def protocol_to_yaml(self, protocol_path: PathLike, yaml_path: PathLike) -> None:
        # protocol_python = open(protocol_path).readlines()

        # metadata = self._find_protocol_metadata(protocol_python)
        # labware = self._find_protocol_labware(protocol_python)
        # pipettes = self._find_protocol_pipettes(protocol_python)
        # commands = []

        pass

    def _find_protocol_metadata(self, protocol_python: List[str]) -> Union[None, Dict]:
        metadata = None
        metadata_flag = False
        for line in protocol_python:
            if "metadata" in line or metadata_flag:
                if metadata is None:
                    metadata = ["{"]
                    metadata_flag = True

                if "{" in line and "}" in line:
                    metadata = line.split("=")[-1]
                    metadata = json.loads(metadata)
                    metadata_flag = False

                else:
                    if line.strip().endswith("{"):
                        continue
                    if line.strip().endswith("}"):
                        metadata_flag = False
                        metadata.append("}")
                        metadata = json.loads("".join(metadata))
                        continue

                    metadata.append(line)

        return metadata

    def _find_protocol_labware(self, protocol_python: List[str]) -> List[str]:

        labware = {}
        for line in protocol_python:
            if "load_labware" in line:
                line = line.split("(")[-1].replace(")", "")
                labware_name, location = line.split(",")
                labware_name = labware_name.strip().replace('"', "")
                location = location.strip().replace('"', "")
                labware[labware_name] = location

        return labware

    def _find_protocol_pipettes(self, protocol_python: List[str]) -> List[str]:

        pipettes = {}
        for line in protocol_python:
            if "load_instrument" in line:
                line = line.split("(")[-1].replace(")", "")
                pipette_name, mount, *_tipracks = line.split(",")
                pipette_name = pipette_name.strip().replace('"', "")
                mount = mount.strip().replace('"', "")
                pipettes[pipette_name] = mount

        return pipettes

    def _find_protocol_instructions(self, protocol_python: List[str]) -> List[str]:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--config", help="YAML config file", type=str, required=True
    )
    args = parser.parse_args()
    return args


def main(config_path):
    # TODO: Think about how a user would want to interact with this, do they want to interact with something like a
    # SeqIO from Biopython? Or more like a interpreter kind of thing? That will guide some of this... not sure where
    # its going right now
    ppiler = ProtoPiler()

    ppiler.yaml_to_protocol(
        config_path=config_path,
        out_file="./test_protocol.py",
        resource_file="./test_resources.json",
        resource_tracking=True,
        reset_when_done=True,
    )


if __name__ == "__main__":
    args = parse_args()
    main(args.config)
