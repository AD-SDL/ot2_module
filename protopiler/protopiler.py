import re
import yaml
import json
import argparse
from pathlib import Path
from itertools import repeat
from typing import List, Optional, TypeVar, Union, Dict, Type

from pydantic import BaseSettings as _BaseSettings

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


class Pipette(BaseSettings):
    name: str
    mount: str


# Command containers
class Instruction(BaseSettings):
    directive: Optional[str] = None
    dim: Optional[str] = None
    iters: Optional[int] = None


class Command(BaseSettings):
    name: Optional[str]
    source: Union[List[str], str]
    destination: Union[str, List[str]]
    volume: Union[int, List[int]]
    instruction: Optional[Instruction] = None
    drop_tip: bool = True


class Commands(BaseSettings):
    commands: List[Command]


# metadata container
class Metadata(BaseSettings):
    protocolName: Optional[str]
    author: Optional[str]
    description: Optional[str]
    apiLevel: Optional[str] = "2.12"


class ProtoPiler:
    def __init__(self, config_path: PathLike, template_dir: PathLike = Path("./protocol_templates")) -> None:
        self.template_dir = template_dir
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

        if isinstance(self.config, dict) and "equipment" in self.config and "commands" in self.config:
            # load metadata, optional
            self.metadata = self.config.get("metadata", None)

            # load the labware
            for data in self.config["equipment"]:
                if isinstance(data, dict) and len(data) == 1:  # it is in form {"name": {'info': info }}
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
            self.commands = Commands(commands=[Command(**data) for data in self.config["commands"]])

        else:
            raise Exception("Unknown configuration file format")

        if len(self.labware) == 0:
            raise Exception("No labware present in config")
        if len(self.pipettes) == 0:
            raise Exception("No pippetes present")

        # generate name -> location and location -> name relationships for labware
        self.labware_to_location = {}
        self.location_to_labware = {}

        self.pipette_to_mount = {}
        self.mount_to_pipette = {}

        for element in self.labware:
            if element.name in self.labware_to_location:
                self.labware_to_location[element.name].append(element.location)
            else:
                self.labware_to_location[element.name] = [element.location]

            if element.location in self.location_to_labware:
                raise Exception("Labware location overloaded, please check configuration")
            self.location_to_labware[element.location] = element.name

        for element in self.pipettes:
            if element.mount in self.mount_to_pipette:
                raise Exception("Pipette location overloaded, please check configuration")

            self.mount_to_pipette[element.mount] = element.name

            if element.name in self.pipette_to_mount:
                self.pipette_to_mount[element.name].append(element.mount)
            else:
                self.pipette_to_mount[element.name] = [element.mount]

    def yaml_to_protocol(self, out_file: PathLike) -> None:

        protocol = []

        # Header and run() declaration with initial deck and pipette dicts
        header = open((self.template_dir / "header.template")).read()
        if self.metadata is not None:
            header = header.replace("#metadata#", f"metadata = {json.dumps(self.metadata, indent=4)}")
        else:
            header = header.replace("#metadata#", "")
        protocol.append(header)

        # load labware and pipette
        protocol.append("\n\t# load labware")

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
            valid_tipracks = self._find_valid_tipracks(name)
            if len(valid_tipracks) == 0:
                print(f"Warning, no tipracks found for: {name}")
            pipette_command = pipette_command.replace("#tip_racks#", ",".join(valid_tipracks))
            protocol.append(pipette_command)

        # execute commands
        protocol.append("\n\t# execute commands")
        commands_python = self._create_commands()
        protocol.extend(commands_python)

        # TODO: anything to write for closing?

        with open(out_file, "w") as f:
            f.write("\n".join(protocol))

    def _find_valid_tipracks(self, pipette_name: str) -> List[str]:

        pip_volume_pattern = re.compile(r"p\d{2,}")
        rack_volume_pattern = re.compile(r"\d{2,}ul$")
        # find suitable tipracks
        pip_volume = int(pip_volume_pattern.search(pipette_name).group().replace("p", ""))
        valid_tipracks = []
        for labware_name, locations in self.labware_to_location.items():
            matches = rack_volume_pattern.search(labware_name)
            if matches is not None:
                vol = int(matches.group().replace("ul", ""))
                if vol == pip_volume:
                    for location in locations:
                        valid_tipracks.append(f'deck["{location}"]')

        return valid_tipracks

    def _create_commands(
        self,
    ) -> List[str]:
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
        for i, command_block in enumerate(self.commands.commands):

            block_name = command_block.name if command_block.name is not None else f"command {i}"
            commands.append(f"\n\t# {block_name}")
            for (volume, src, dst) in self._process_instruction(command_block):
                # determine which pipette to use
                pipette_mount = self._determine_instrument(volume)
                if pipette_mount is None:
                    raise Exception(f"No pipette available for {block_name} with volume: {volume}")

                # check for tip
                if not tip_loaded[pipette_mount]:
                    load_command = pick_tip_template.replace("#pipette#", f'pipettes["{pipette_mount}"]')
                    commands.append(load_command)
                    tip_loaded[pipette_mount] = True

                # aspirate and dispense
                # find wellplate TODO: what happens with more than one wellplate
                # should accomodate in find wellplate method
                wellplate_location = self._find_wellplate()
                if wellplate_location is None:
                    raise Exception("No wellplate found")

                aspirate_command = aspirate_template.replace("#pipette#", f'pipettes["{pipette_mount}"]')
                aspirate_command = aspirate_command.replace("#volume#", str(volume))
                aspirate_command = aspirate_command.replace("#src#", f'deck["{wellplate_location}"]["{src}"]')
                commands.append(aspirate_command)

                dispense_command = dispense_template.replace("#pipette#", f'pipettes["{pipette_mount}"]')
                dispense_command = dispense_command.replace("#volume#", str(volume))
                dispense_command = dispense_command.replace("#dst#", f'deck["{wellplate_location}"]["{dst}"]')
                commands.append(dispense_command)

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

    def _determine_instrument(self, target_volume: int) -> str:
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

    def _find_wellplate(self) -> str:
        location = None

        for name, loc in self.labware_to_location.items():
            if "well" in name:
                if location is not None:
                    print(f"Location {location} is overwritten with {loc}, multiple wellplates present")
                if type(loc) is list:
                    # TODO: determine correct one to take if more than one wellplate, currently take first one
                    location = loc[0]
                elif type(loc) is str:
                    location = loc

        return location

    def _process_instruction(self, command_block: Command) -> List[str]:
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
                        raise Exception("Multiple iterables found, cannot deterine dimension to iterate over")
                iter_len = len(command_block.source)
            if isinstance(command_block.destination, list):
                if iter_len != 0 and len(command_block.destination) != iter_len:
                    # handle if forgot to change list of one value to scalar
                    if len(command_block.destination) == 1:
                        command_block.destination = command_block.destination[0]
                    else:
                        raise Exception("Multiple iterables found, cannot deterine dimension to iterate over")
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
    Everything under here is for getting a config from an existing protocol
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
                    print(line)
                    print("one-liner")
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
                print(line)
                pipette_name, mount, *_tipracks = line.split(",")
                pipette_name = pipette_name.strip().replace('"', "")
                mount = mount.strip().replace('"', "")
                pipettes[pipette_name] = mount

        print(pipettes)

        return pipettes

    def _find_protocol_instructions(self, protocol_python: List[str]) -> List[str]:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", help="YAML config file", type=str, required=True)
    args = parser.parse_args()
    return args


def main(config_path):
    ppiler = ProtoPiler(config_path)

    ppiler.yaml_to_protocol(out_file="test_out.py")


if __name__ == "__main__":
    args = parse_args()
    main(args.config)
