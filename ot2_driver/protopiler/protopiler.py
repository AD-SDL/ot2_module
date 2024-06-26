"""Protopiler is designed to compile a config yaml into a working protocol"""
import argparse
import copy
from datetime import datetime
from itertools import repeat
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple, Union

import pandas as pd

from ot2_driver.protopiler.config import (
    Clear_Pipette,
    CommandBase,
    Deactivate,
    Mix,
    Move_Pipette,
    Multi_Transfer,
    PathLike,
    ProtocolConfig,
    Replace_Tip,
    Resource,
    Temperature_Set,
    Transfer,
)
from ot2_driver.protopiler.resource_manager import ResourceManager

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
    """Class that takes in a parses configs and outputs a completed protocol.py file"""

    def __init__(
        self,
        config_path: Optional[PathLike] = None,
        template_dir: PathLike = (
            Path(__file__).parent.resolve() / "protocol_templates"
        ),
        resource_file: Optional[PathLike] = None,
    ) -> None:
        """Can initialize with the resources we need, or it can be done after initialization

        Parameters
        ----------
        config_path : Optional[PathLike], optional
            path to the yaml configuration, by default None
        template_dir : PathLike, optional
            path to the template directory, by default Path("./protocol_templates")
        resource_file : Optional[PathLike], optional
            path to the resource file, if using a config and it does not exist, it will be created, by default None
        """
        self.template_dir = template_dir
        self.resource_file = resource_file

        if self.resource_file:
            self.resource_file = Path(self.resource_file)

        self.config = None
        if config_path:
            self.load_config(config_path=config_path, resource_file=resource_file)

    def load_config(
        self,
        config_path: PathLike,
        resource_file: Optional[PathLike] = None,
        resource_path: Optional[PathLike] = None,
        protocol_out_path: Optional[PathLike] = None,
    ) -> None:
        """Loading the config and generating necessary information for compiling a config

        This is what allows for nothing to be passed in during obj creation, if a user calls
        this method, it will load all the necessary things
        Parameters
        ----------
        config_path : PathLike
            path to the configuration file
        resource_file : Optional[PathLike], optional
            path to the resource file, if does not exist it will be created, by default None
        """
        self.config_path = config_path
        self.resource_file = resource_file
        self.resource_path = resource_path
        self.protocol_out_path = protocol_out_path
        self.config = ProtocolConfig.from_yaml(config_path)

        self.load_resources(self.config.resources)
        self.metadata = self.config.metadata
        self.resource_manager = ResourceManager(
            self.config.equipment, self.resource_file
        )

        self.commands = self.config.commands
        self._postprocess_commands()

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
        if self.resources:
            resource_key = list(self.resources.keys())[0]
        for command in self.commands:
            if isinstance(command, Transfer):
                if ":[" in command.source:
                    command.source = self._unpack_alias(command_elem=command.source)

                # Add logic for taking well names from files
                # peek into the source, check the well destination part
                peek_elem = command.source
                if isinstance(command.source, list):  # No mixing and matching
                    peek_elem = command.source[0]

                peek_well: str = peek_elem.split(":")[-1]
                # check if it follows naming convention`[A-Z,a-z]?[0-9]{1,3}`
                # TODO better way to check the naming conventions for the wells
                if (
                    not peek_well.isdigit()
                    and not peek_well[1:].isdigit()
                    and "payload" not in peek_well
                ):
                    # read from file
                    new_locations = []
                    for orig_command, loc in zip(
                        repeat(command.source), self.resources[resource_key][peek_well]
                    ):
                        orig_deck_location = orig_command.split(":")[0]
                        new_locations.append(f"{orig_deck_location}:{loc}")

                    command.source = new_locations
                if ":[" in command.destination:
                    command.destination = self._unpack_alias(command.destination)

                # Add logic for reading well names from file
                # peek into the source, check the well destination part
                peek_elem = command.destination
                if isinstance(command.destination, list):  # No mixing and matching
                    peek_elem = command.destination[0]

                peek_well: str = peek_elem.split(":")[-1]
                if isinstance(command.destination, list):  # No mixing and matching
                    peek_elem = command.destination[0]
                if (
                    not peek_well.isdigit()
                    and not peek_well[1:].isdigit()
                    and "payload" not in peek_well
                ):
                    # read from file
                    new_locations = []
                    for orig_command, loc in zip(
                        repeat(command.destination),
                        self.resources[resource_key][peek_well],
                    ):
                        orig_deck_location = orig_command.split(":")[0]
                        new_locations.append(f"{orig_deck_location}:{loc}")

                    command.destination = new_locations
                # have to check if volumes comes from the files
                if (
                    not isinstance(command.volume, int)
                    and not isinstance(command.volume, list)
                    and (
                        hasattr(command.volume, "__contains__")
                        and "payload" not in command.volume
                    )
                ):
                    new_volumes = []
                    for vol in self.resources[resource_key][command.volume]:
                        new_volumes.append(int(vol))

                        command.volume = new_volumes
            if isinstance(command, Mix):
                if ":[" in command.location:
                    command.location = self._unpack_alias(command.location)

                # Add logic for reading well names from file
                # peek into the source, check the well destination part
                peek_elem = command.location
                if isinstance(command.location, list):  # No mixing and matching
                    peek_elem = command.location[0]

                peek_well: str = peek_elem.split(":")[-1]
                if isinstance(command.location, list):  # No mixing and matching
                    peek_elem = command.location[0]

                # external file
                if (
                    not peek_well.isdigit()
                    and not peek_well[1:].isdigit()
                    and "payload" not in peek_well
                ):
                    # read from file
                    new_locations = []
                    for orig_command, loc in zip(
                        repeat(command.location),
                        self.resources[resource_key][peek_well],
                    ):
                        orig_deck_location = orig_command.split(":")[0]
                        new_locations.append(f"{orig_deck_location}:{loc}")

                    command.location = new_locations

            if isinstance(command, Multi_Transfer):
                if ":[" in command.multi_source:
                    command.multi_source = self._unpack_multi_alias(
                        command_elem=command.multi_source
                    )

                # Add logic for taking well names from files
                # peek into the source, check the well destination part
                peek_elem = command.multi_source
                if isinstance(command.multi_source, list):  # No mixing and matching
                    peek_elem = command.multi_source[0]
                peek_well = peek_elem.split(":")[-1]
                # check if it follows naming convention`[A-Z,a-z]?[0-9]{1,3}`
                # TODO better way to check the naming conventions for the wells
                peek_well = peek_well.split(", ")
                if len(peek_well) == 1 and "payload" not in peek_well:
                    # read from file
                    new_locations = []
                    for orig_command, loc in zip(
                        repeat(command.multi_source),
                        self.resources[resource_key][peek_well[0]],
                    ):
                        orig_deck_location = orig_command.split(":")[0]
                        new_locations.append(f"{orig_deck_location}:{loc}")

                    command.multi_source = new_locations
                if ":[" in command.multi_destination:
                    command.multi_destination = self._unpack_multi_alias(
                        command.multi_destination
                    )

                # Add logic for reading well names from file
                # peek into the source, check the well destination part
                peek_elem = command.multi_destination
                if isinstance(
                    command.multi_destination, list
                ):  # No mixing and matching
                    peek_elem = command.multi_destination[0]

                peek_well = peek_elem.split(":")[-1]
                peek_well = peek_well.split(", ")
                if len(peek_well) == 1 and "payload" not in peek_well:
                    # read from file
                    new_locations = []
                    for orig_command, loc in zip(
                        repeat(command.multi_destination),
                        self.resources[resource_key][peek_well[0]],
                    ):
                        orig_deck_location = orig_command.split(":")[0]
                        new_locations.append(f"{orig_deck_location}:{loc}")

                    command.multi_destination = new_locations
                # have to check if volumes comes from the files
                if (
                    not isinstance(command.multi_volume, int)
                    and not isinstance(command.multi_volume, list)
                    and (
                        hasattr(command.multi_volume, "__contains__")
                        and "payload" not in command.multi_volume
                    )
                ):
                    new_volumes = []
                    for vol in self.resources[resource_key][command.multi_volume]:
                        new_volumes.append(int(vol))

                        command.multi_volume = new_volumes

    def _unpack_alias(self, command_elem: Union[str, List[str]]) -> List[str]:
        new_locations = []
        alias = command_elem.split(":")[0]
        process_source = copy.deepcopy(command_elem)
        process_source = ":".join(process_source.split(":")[1:])
        # split and rejoin after first colon
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

        return new_locations

    def _unpack_multi_alias(
        self, command_elem: Union[str, List[List[str]]]
    ) -> List[List[str]]:
        new_locations = []
        alias = command_elem.split(":")[0]
        process_source = copy.deepcopy(command_elem)
        process_source = ":".join(process_source.split(":")[1:])
        process_source = process_source.strip("][").split("], [")

        for i in range(len(process_source)):
            process_source[i] = process_source[i].split(", ")
        for location in process_source:
            if len(location) == 0:
                continue
            new_location = None
            if ":" not in location:
                new_location = f"{alias}:{location}"
                new_locations.append(new_location)
            else:
                new_locations.append(new_location)
        return new_locations

    def load_resources(self, resources: List[Resource]):
        """Load the other resources (files) specified in the config

        Currently only accepts *.xls or *.xlsx files

        Parameters
        ----------
        resources : List[Resource]
            the dataclasses of resource objects

        """
        self.resources = {}

        if resources:
            for resource in resources:
                self.resources[resource.name] = pd.read_excel(
                    resource.location, header=0
                )

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
        payload: Optional[Dict] = None,
        protocol_out_path: PathLike = Path(
            f"./protocol_{datetime.now().strftime('%Y%m%d-%H%M%S')}.py"
        ),
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
            path to yaml configuration file, if not present, will look to self, by default None
        protocol_out : PathLike, optional
            path to save the protocol to, by default Path(f"./protocol_{datetime.now().strftime('%Y%m%d-%H%M%S')}.py")
        resource_file : Optional[PathLike], optional
           path to existing resource file, if config is used, it will be created, by default None
        resource_file_out : Optional[PathLike], optional
            if you want to specify the creation of new resource file, by default None
        write_resources : bool, optional
            whether you want to save the resource file or clean it up, by default True
        overwrite_resources_json : bool, optional
            whether you want to rewrite a resource file, by default True
        reset_when_done : bool, optional
            whether to reset the class when finished compiling, by default False

        Returns
        -------
        Tuple[Path]
            returns the path to the protocol.py file as well as the resource file (if it does not exist, None)
        """

        if not self.config:
            self.load_config(config_path)

        if resource_file and not self.resource_file:
            self.load_config(self.config_path, resource_file)

        if self.protocol_out_path is None:
            protocol_out = Path(
                f"./protocol_{datetime.now().strftime('%Y%m%d-%H%M%S')}.py"
            )
        else:
            protocol_out = Path(
                self.protocol_out_path
                + f"/protocol_{datetime.now().strftime('%Y%m%d-%H%M%S')}.py"
            )

        protocol = []

        # Header and run() declaration with initial deck and pipette dicts
        header = open((self.template_dir / "header.template")).read()
        if self.metadata is not None:
            header = header.replace(
                "#metadata#", f"metadata = {self.metadata.model_dump_json(indent=4)}"
            )
        else:
            header = header.replace("#metadata#", "")
        protocol.append(header)

        # load labware and pipette
        protocol.append(
            "\n    ################\n    # load labware #\n    ################"
        )

        labware_block = open((self.template_dir / "load_labware.template")).read()
        module_block = open((self.template_dir / "load_module.template")).read()
        offset_block = open((self.template_dir / "labware_offset.template")).read()
        # TODO: think of some better software design for accessing members of resource manager
        for location, name in self.resource_manager.location_to_labware.items():
            match = False
            for loc, nm in self.resource_manager.module_info.items():
                if loc == location:
                    labware_command = module_block.replace("#module_name#", f'"{nm}"')
                    labware_command = labware_command.replace(
                        "#location#", f'"{location}"'
                    )
                    labware_command = labware_command.replace(
                        "#nickname#", f'{"module"}'
                    )
                    labware_command = labware_command.replace(
                        "#labware_name#", f'"{name}"'
                    )
                    match = True

            if not match:
                labware_command = labware_block.replace("#name#", f'"{name}"')
                labware_command = labware_command.replace("#location#", f'"{location}"')

            protocol.append(labware_command)

            for loc, off in self.resource_manager.offset_to_location.items():
                if loc == location:
                    offset_command = offset_block.replace("#x_offset#", f"{off[0]}")
                    offset_command = offset_command.replace("#y_offset#", f"{off[1]}")
                    offset_command = offset_command.replace("#z_offset#", f"{off[2]}")
                    offset_command = offset_command.replace(
                        "#location#", f'"{location}"'
                    )

                    protocol.append(offset_command)

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
        protocol.append(
            "\n    ####################\n    # execute commands #\n    ####################"
        )

        commands_python = self._create_commands(payload=payload)
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
            resource_file_out = self.resource_manager.dump_resource_json(
                out_file=resource_file_out
            )

        elif resource_file and write_resources:
            resource_file_out = self.resource_manager.dump_resource_json(
                out_file=resource_file
            )

        elif self.resource_file and write_resources and overwrite_resources_json:
            resource_file_out = self.resource_manager.dump_resource_json(
                out_file=self.resource_file
            )

        elif write_resources:
            resource_file_out = self.resource_manager.dump_resource_json()

        if reset_when_done:
            self._reset()

        return protocol_out, resource_file_out

    def _create_commands(self, payload: Optional[Dict]) -> List[str]:
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
        return_tip_template = open((self.template_dir / "return_tip.template")).read()
        mix_template = open((self.template_dir / "mix.template")).read()
        dispense_clearance_template = open(
            (self.template_dir / "dispense_clearance.template")
        ).read()
        aspirate_clearance_template = open(
            (self.template_dir / "aspirate_clearance.template")
        ).read()
        blow_out_template = open((self.template_dir / "blow_out.template")).read()
        temp_change_template = open(
            (self.template_dir / "set_temperature.template")
        ).read()
        deactivate_template = open((self.template_dir / "deactivate.template")).read()
        move_template = open((self.template_dir / "move_pipette.template")).read()
        tip_loaded = {"left": False, "right": False}
        for i, command_block in enumerate(self.commands):
            block_name = (
                command_block.name if command_block.name is not None else f"command {i}"
            )
            commands.append(f"\n    # {block_name}")
            # TODO: Inject the payload here
            # Inject the payload
            if isinstance(payload, dict):
                (arg_keys, arg_values) = zip(*command_block.__dict__.items())
                for key, value in payload.items():
                    if "payload." not in key:
                        key = f"payload.{key}"
                    if key in arg_values:
                        idx = arg_values.index(key)
                        step_arg_key = arg_keys[idx]
                        # this feels slimy...
                        setattr(command_block, step_arg_key, value)
            if isinstance(command_block, Transfer):
                for (
                    volume,
                    src,
                    dst,
                    mix_cycles,
                    mix_vol,
                    asp_height,
                    disp_height,
                    blow_out,
                    drop_tip,
                    return_tip,
                ) in self._process_instruction(command_block):
                    if volume <= 0:
                        pass
                    else:
                        # determine which pipette to use
                        pipette_mount = self.resource_manager.determine_pipette(
                            volume, False
                        )
                        print(pipette_mount)
                        if pipette_mount is None:
                            raise Exception(
                                f"No pipette available for {block_name} with volume: {volume}"
                            )
                        # check for tip
                        if not tip_loaded[pipette_mount]:
                            load_command = pick_tip_template.replace(
                                "#pipette#", f'pipettes["{pipette_mount}"]'
                            )
                            # TODO: think of some better software design for accessing members of resource manager
                            pipette_name = self.resource_manager.mount_to_pipette[
                                pipette_mount
                            ]

                            # TODO: define flag to grab from specific well or just use the ones defined by the OT2
                            if True:
                                (
                                    rack_location,
                                    well_location,
                                ) = self.resource_manager.get_next_tip(pipette_name, 1)
                                location_string = (
                                    f'deck["{rack_location}"].wells()[{well_location}]'
                                )
                                load_command = load_command.replace(
                                    "#location#", location_string
                                )
                            else:
                                load_command = load_command.replace("#location#", "")
                                self.resource_manager.update_tip_usage(pipette_name)

                            commands.append(load_command)
                            tip_loaded[pipette_mount] = True

                        # aspirate and dispense
                        # set aspirate clearance
                        aspirate_clearance_command = (
                            aspirate_clearance_template.replace(
                                "#pipette#", f'pipettes["{pipette_mount}"]'
                            )
                        )
                        aspirate_clearance_command = aspirate_clearance_command.replace(
                            "#height#", str(asp_height)
                        )
                        commands.append(aspirate_clearance_command)
                        src_wellplate_location = self._parse_wellplate_location(src)
                        # should handle things not formed like loc:well
                        src_well = src.split(":")[-1]

                        aspirate_command = aspirate_template.replace(
                            "#pipette#", f'pipettes["{pipette_mount}"]'
                        )
                        aspirate_command = aspirate_command.replace(
                            "#volume#", str(volume)
                        )
                        aspirate_command = aspirate_command.replace(
                            "#src#", f'deck["{src_wellplate_location}"]["{src_well}"]'
                        )
                        commands.append(aspirate_command)
                        self.resource_manager.update_well_usage(
                            src_wellplate_location, src_well
                        )

                        # set dispense clearance
                        dispense_clearance_command = (
                            dispense_clearance_template.replace(
                                "#pipette#", f'pipettes["{pipette_mount}"]'
                            )
                        )
                        dispense_clearance_command = dispense_clearance_command.replace(
                            "#height#", str(disp_height)
                        )
                        commands.append(dispense_clearance_command)

                        dst_wellplate_location = self._parse_wellplate_location(dst)
                        dst_well = dst.split(":")[
                            -1
                        ]  # should handle things not formed like loc:well
                        dispense_command = dispense_template.replace(
                            "#pipette#", f'pipettes["{pipette_mount}"]'
                        )
                        dispense_command = dispense_command.replace(
                            "#volume#", str(volume)
                        )
                        dispense_command = dispense_command.replace(
                            "#dst#", f'deck["{dst_wellplate_location}"]["{dst_well}"]'
                        )
                        commands.append(dispense_command)
                        # update resource usage
                        self.resource_manager.update_well_usage(
                            dst_wellplate_location, dst_well
                        )

                        if mix_cycles is not None:
                            if mix_cycles >= 1:
                                # hardcoded to destination well for now
                                mix_command = mix_template.replace(
                                    "#pipette#", f'pipettes["{pipette_mount}"]'
                                )
                                mix_command = mix_command.replace(
                                    "#volume#", str(mix_vol)
                                )
                                mix_command = mix_command.replace(
                                    "#loc#",
                                    f'deck["{dst_wellplate_location}"]["{dst_well}"]',  # same as destination
                                )
                                mix_command = mix_command.replace(
                                    "#reps#", str(mix_cycles)
                                )

                                commands.append(mix_command)

                            # no change in resources
                        if blow_out:
                            blowout_command = blow_out_template.replace(
                                "#pipette#", f'pipettes["{pipette_mount}"]'
                            )
                            commands.append(blowout_command)

                        if drop_tip:
                            drop_command = drop_tip_template.replace(
                                "#pipette#", f'pipettes["{pipette_mount}"]'
                            )
                            commands.append(drop_command)
                            tip_loaded[pipette_mount] = False

                        if return_tip:
                            return_command = return_tip_template.replace(
                                "#pipette#", f'pipettes["{pipette_mount}"]'
                            )
                            commands.append(return_command)
                            tip_loaded[pipette_mount] = False

                        commands.append("")
            elif isinstance(command_block, Multi_Transfer):
                for (
                    volume,
                    src,
                    dst,
                    mix_cycles,
                    mix_vol,
                    asp_height,
                    disp_height,
                    blow_out,
                    drop_tip,
                ) in self._process_multi_instruction(command_block):
                    if volume <= 0:
                        pass
                    else:
                        # determine which pipette to use
                        pipette_mount = self.resource_manager.determine_pipette(
                            volume, True
                        )
                        print(pipette_mount)
                        if pipette_mount is None:
                            raise Exception(
                                f"No pipette available for {block_name} with volume: {volume}"
                            )
                        # check to make sure that appropriate pipette is a multi-channel
                        # TODO: need to change, what if we have single and multi channel of same volume?
                        if (
                            "multi"
                            not in self.resource_manager.mount_to_pipette[pipette_mount]
                        ):
                            raise Exception("Selected pipette is not multi-channel")
                        # check for tip
                        if not tip_loaded[pipette_mount]:
                            load_command = pick_tip_template.replace(
                                "#pipette#", f'pipettes["{pipette_mount}"]'
                            )
                            pipette_name = self.resource_manager.mount_to_pipette[
                                pipette_mount
                            ]
                            new_src = copy.copy(src)
                            new_src = new_src.replace("'", "")
                            new_src = new_src.split(":")[-1]
                            new_src = new_src.strip("][").split(", ")

                            # TODO: define flag to grab from specific well or just use the ones defined by the OT2
                            if True:
                                (
                                    rack_location,
                                    well_location,
                                ) = self.resource_manager.get_next_tip(
                                    pipette_name, len(new_src)
                                )

                                location_string = (
                                    f'deck["{rack_location}"].wells()[{well_location}]'
                                )
                                load_command = load_command.replace(
                                    "#location#", location_string
                                )
                            else:
                                load_command = load_command.replace("#location#", "")
                                self.resource_manager.update_tip_usage(pipette_name)

                            commands.append(load_command)
                            tip_loaded[pipette_mount] = True

                        else:
                            new_src = copy.copy(src)
                            new_src = new_src.replace("'", "")
                            new_src = new_src.split(":")[-1]
                            new_src = new_src.strip("][").split(", ")

                        # aspirate and dispense
                        # set aspirate clearance
                        aspirate_clearance_command = (
                            aspirate_clearance_template.replace(
                                "#pipette#", f'pipettes["{pipette_mount}"]'
                            )
                        )
                        aspirate_clearance_command = aspirate_clearance_command.replace(
                            "#height#", str(asp_height)
                        )
                        commands.append(aspirate_clearance_command)
                        src_wellplate_location = self._parse_wellplate_location(src)
                        # should handle things not formed like loc:well
                        src_well = new_src[0]

                        aspirate_command = aspirate_template.replace(
                            "#pipette#", f'pipettes["{pipette_mount}"]'
                        )
                        aspirate_command = aspirate_command.replace(
                            "#volume#", str(volume)
                        )
                        aspirate_command = aspirate_command.replace(
                            "#src#", f'deck["{src_wellplate_location}"]["{src_well}"]'
                        )
                        commands.append(aspirate_command)

                        self.resource_manager.update_well_usage(
                            src_wellplate_location, new_src
                        )

                        # set dispense clearance
                        dispense_clearance_command = (
                            dispense_clearance_template.replace(
                                "#pipette#", f'pipettes["{pipette_mount}"]'
                            )
                        )
                        dispense_clearance_command = dispense_clearance_command.replace(
                            "#height#", str(disp_height)
                        )
                        commands.append(dispense_clearance_command)

                        dst_wellplate_location = self._parse_wellplate_location(dst)
                        new_dst = copy.copy(dst)
                        new_dst = new_dst.replace("'", "")
                        new_dst = new_dst.split(":")[-1]
                        new_dst = new_dst.strip("][").split(", ")
                        dst_well = new_dst[
                            0
                        ]  # should handle things not formed like loc:well
                        dispense_command = dispense_template.replace(
                            "#pipette#", f'pipettes["{pipette_mount}"]'
                        )
                        dispense_command = dispense_command.replace(
                            "#volume#", str(volume)
                        )
                        dispense_command = dispense_command.replace(
                            "#dst#", f'deck["{dst_wellplate_location}"]["{dst_well}"]'
                        )
                        commands.append(dispense_command)
                        # update resource usage
                        self.resource_manager.update_well_usage(
                            dst_wellplate_location, new_dst
                        )

                        if mix_cycles is not None:
                            if mix_cycles >= 1:
                                # hardcoded to destination well for now
                                mix_command = mix_template.replace(
                                    "#pipette#", f'pipettes["{pipette_mount}"]'
                                )
                                mix_command = mix_command.replace(
                                    "#volume#", str(mix_vol)
                                )
                                mix_command = mix_command.replace(
                                    "#loc#",
                                    f'deck["{dst_wellplate_location}"]["{dst_well}"]',  # same as destination
                                )
                                mix_command = mix_command.replace(
                                    "#reps#", str(mix_cycles)
                                )

                                commands.append(mix_command)

                            # no change in resources
                        if blow_out:
                            blowout_command = blow_out_template.replace(
                                "#pipette#", f'pipettes["{pipette_mount}"]'
                            )
                            commands.append(blowout_command)

                        if drop_tip:
                            drop_command = drop_tip_template.replace(
                                "#pipette#", f'pipettes["{pipette_mount}"]'
                            )
                            commands.append(drop_command)
                            tip_loaded[pipette_mount] = False

                        commands.append("")
            elif isinstance(command_block, Temperature_Set):
                temp_change_command = temp_change_template.replace(
                    "#temp#", str(command_block.change_temp)
                )
                commands.append(temp_change_command)

            elif isinstance(command_block, Mix):


                if (
                    isinstance(command_block.location, str)
                    and isinstance(command_block.reps, int)
                    and isinstance(command_block.mix_volume, float)
                ):
                    pipette_mount = self.resource_manager.determine_pipette(
                    command_block.mix_volume, False
                )
                    if pipette_mount is None:
                        raise Exception(
                            f"No pipette available for {block_name} with volume: {command_block.mix_volume}"
                        )
                    #TODO: make more robust
                    # # check for tip
                    if not tip_loaded[pipette_mount]:

                        load_command = pick_tip_template.replace(
                            "#pipette#", f'pipettes["{pipette_mount}"]'
                        )
                        pipette_name = self.resource_manager.mount_to_pipette[
                            pipette_mount
                        ]

                        # TODO: define flag to grab from specific well or just use the ones defined by the OT2
                        if True:
                            (
                                rack_location,
                                well_location,
                            ) = self.resource_manager.get_next_tip(pipette_name, 1)
                            location_string = (
                                f'deck["{rack_location}"].wells()[{well_location}]'
                            )
                            load_command = load_command.replace(
                                "#location#", location_string
                            )
                        else:
                            load_command = load_command.replace("#location#", "")
                            self.resource_manager.update_tip_usage(pipette_name)
                    
                        commands.append(load_command)
                        tip_loaded[pipette_mount] = True
                



                    mix_command = mix_template.replace(
                        "#reps#", str(command_block.reps)
                    )
                    mix_command = mix_command.replace(
                        "#volume#", str(command_block.mix_volume)
                    )
                    wellplate_location = self._parse_wellplate_location(
                        command_block.location
                    )
                    well = command_block.location.split(":")[-1]
                    mix_command = mix_command.replace(
                        "#loc#", f'deck["{wellplate_location}"]["{well}"]'
                    )
                    mix_command = mix_command.replace(
                        "#pipette#", f'pipettes["{pipette_mount}"]'
                    )
                    commands.append(mix_command)

                else:
                    iter_len = 0
                    if isinstance(command_block.location, list):
                        if len(command_block.location) == 1:
                            command_block.location = command_block.location[0]
                        else:
                            iter_len = len(command_block.location)

                    if isinstance(command_block.mix_volume, list):
                        if iter_len != 0 and len(command_block.mix_volume) != iter_len:
                            if len(command_block.mix_volume) == 1:
                                command_block.mix_volume = command_block.mix_volume[0]
                            else:
                                raise Exception(
                                    "Multiple iterables found, cannot determine dimension to iterate over"
                                )
                        iter_len = len(command_block.mix_volume)

                    if isinstance(command_block.reps, list):
                        if iter_len != 0 and len(command_block.reps) != iter_len:
                            if len(command_block.reps) == 1:
                                command_block.reps = command_block.reps[0]
                            else:
                                raise Exception(
                                    "Multiple iterables found, cannot determine dimension to iterate over"
                                )
                        iter_len = len(command_block.reps)

                    if not isinstance(command_block.location, list):
                        locations = repeat(command_block.location, iter_len)
                    else:
                        locations = command_block.location

                    if not isinstance(command_block.mix_volume, list):
                        mix_volumes = repeat(command_block.mix_volume, iter_len)
                    else:
                        mix_volumes = command_block.mix_volume

                    if not isinstance(command_block.reps, list):
                        mix_reps = repeat(command_block.reps, iter_len)
                    else:
                        mix_reps = command_block.reps

                    pipette_mount = self.resource_manager.determine_pipette(
                    command_block.mix_volume, False
                    )

                    if pipette_mount is None:
                        raise Exception(
                            f"No pipette available for {block_name} with volume: {command_block.mix_volume}"
                        )
                    # # check for tip
                    if not tip_loaded[pipette_mount]:

                        load_command = pick_tip_template.replace(
                            "#pipette#", f'pipettes["{pipette_mount}"]'
                        )
                        pipette_name = self.resource_manager.mount_to_pipette[
                            pipette_mount
                        ]

                        # TODO: define flag to grab from specific well or just use the ones defined by the OT2
                        if True:
                            (
                                rack_location,
                                well_location,
                            ) = self.resource_manager.get_next_tip(pipette_name, 1)
                            location_string = (
                                f'deck["{rack_location}"].wells()[{well_location}]'
                            )
                            load_command = load_command.replace(
                                "#location#", location_string
                            )
                        else:
                            load_command = load_command.replace("#location#", "")
                            self.resource_manager.update_tip_usage(pipette_name)
                    
                        commands.append(load_command)
                        tip_loaded[pipette_mount] = True

                    for loc, mix_vols, rep in zip(locations, mix_volumes, mix_reps):
                        mix_command = mix_template.replace("#reps#", str(rep))
                        mix_command = mix_command.replace("#volume#", str(mix_vols))
                        wellplate_location = self._parse_wellplate_location(loc)
                        well = loc.split(":")[-1]
                        mix_command = mix_command.replace(
                            "#loc#", f'deck["{wellplate_location}"]["{well}"]'
                        )
                        mix_command = mix_command.replace(
                            "#pipette#", f'pipettes["{pipette_mount}"]'
                        )
                        commands.append(mix_command)

            elif isinstance(command_block, Deactivate):
                if not isinstance(command_block.deactivate, bool):
                    raise Exception("deactivate command must be bool")
                deactivate_command = deactivate_template.replace("#turn_off#", "")
                commands.append(deactivate_command)

            elif isinstance(command_block, Replace_Tip):
                if not isinstance(command_block.replace_tip, bool):
                    raise Exception("replace_tip must be bool")
                # check if tip on pipette
                if tip_loaded[pipette_mount] == False:
                    print("NO TIP TO REPLACE")
                else:
                    replace_tip_command = return_tip_template.replace(
                        "#pipette#", f'pipettes["{pipette_mount}"]'
                    )
                    commands.append(replace_tip_command)
                    tip_loaded[pipette_mount] = False

            elif isinstance(command_block, Clear_Pipette):
                if not isinstance(command_block.clear, bool):
                    raise Exception("clear command must be True or False")

                clear_command = drop_tip_template.replace(
                    "#pipette#", f'pipettes["{pipette_mount}"]'
                )
                commands.append(clear_command)
                tip_loaded[pipette_mount] = False

            elif isinstance(command_block, Move_Pipette):
                if not isinstance(command_block.move_to, int):
                    raise Exception("Given deck position must be an int")
                if command_block.move_to > 12 or command_block.move_to < 1:
                    raise Exception("number must be a valid deck position 1-12")
                # TODO: need to establish pipette mount to move
                # pipette_mount = self.resource_manager.pipette_to_mount[]
                move_command = move_template.replace(
                    "#pipette#", f'pipettes["{pipette_mount}"]'
                )
                move_command = move_command.replace(
                    "#location#", str(command_block.move_to)
                )
                commands.append(move_command)
            else:
                raise Exception(
                    f"Command {command_block} not recognized, check that the command is formatted correctly"
                )

        for mount, status in tip_loaded.items():
            if status:
                commands.append(
                    drop_tip_template.replace("#pipette#", f'pipettes["{mount}"]')
                )
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
        # new format, pass a wellplate location, then well location
        if ":" in command_location:
            try:
                plate, _ = command_location.split(":")
            except ValueError as e:
                raise Exception(
                    f"Command: {command_location} is not formatted correctly..."
                ) from e
            # TODO: think of some better software design for accessing members of resource manager
            location = self.resource_manager.alias_to_location[plate]
        else:  # older format of passing location
            for name, loc in self.resource_manager.labware_to_location.items():
                if "well" in name:
                    if location is not None:
                        print(
                            f"Location {location} is overwritten with {loc}, multiple wellplates present"
                        )
                    if isinstance(loc, list) and len(loc) > 1:
                        print(
                            f"Ambiguous command '{command_location}', multiple plates satisfying params (locations: {loc}) found, choosing location: {loc[0]}..."
                        )
                        location = loc[0]
                    elif isinstance(loc, list) and len(loc) == 1:
                        location = loc[0]
                    elif isinstance(loc, str):
                        location = loc

        return location

    def _process_instruction(
        self, command_block: CommandBase
    ) -> Generator[list, None, None]:
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
        # Ensure that the command block is a properly validated Transfer
        command_block = Transfer.model_validate(command_block)
        if (
            isinstance(command_block.volume, float)
            and isinstance(command_block.source, str)
            and isinstance(command_block.destination, str)
            and isinstance(command_block.mix_cycles, int)
            and isinstance(command_block.mix_volume, int)
            and isinstance(command_block.aspirate_clearance, (float, int))
            and isinstance(command_block.dispense_clearance, (float, int))
            and isinstance(command_block.blow_out, bool)
            and isinstance(command_block.drop_tip, bool)
            and isinstance(command_block.return_tip, bool)
        ):
            yield (
                command_block.volume,
                command_block.source,
                command_block.destination,
                command_block.mix_cycles,
                command_block.mix_volume,
                command_block.aspirate_clearance,
                command_block.dispense_clearance,
                command_block.blow_out,
                command_block.drop_tip,
                command_block.return_tip,
            )
        else:
            # could be one source (either list of volumes or one volume) to many destination
            # could be many sources (either list of volumes or one volume) to one destination
            # could be one source/destination, many volumes

            # TODO: think about optimizations. e.g if you are dispensing from one well to multiple
            # destinations, we could pick up the sum of the volumes and drop into each well without
            # the whole dispense, drop tip, pick up tip, aspirate in the middle

            for row in zip(
                command_block.volume,
                command_block.source,
                command_block.destination,
                command_block.mix_cycles,
                command_block.mix_volume,
                command_block.aspirate_clearance,
                command_block.dispense_clearance,
                command_block.blow_out,
                command_block.drop_tip,
                command_block.return_tip,
            ):
                yield row

    def _process_multi_instruction(
        self, command_block: CommandBase
    ) -> Generator[list, None, None]:
        """mimics _process_instruction but for multi channel transfers"""

        # Ensure that the command block is a properly validated Multi_Transfer
        command_block = Multi_Transfer.model_validate(command_block)

        for row in zip(
            command_block.multi_volume,
            command_block.multi_source,
            command_block.multi_destination,
            command_block.multi_mix_cycles,
            command_block.multi_mix_volume,
            command_block.multi_aspirate_clearance,
            command_block.multi_dispense_clearance,
            command_block.multi_blow_out,
            command_block.multi_drop_tip,
        ):
            yield row


def main(args):  # noqa: D103
    protopiler = ProtoPiler(args.config)

    protopiler.yaml_to_protocol(
        config_path=args.config,
        protocol_out_path=args.protocol_out,
        resource_file=args.resource_in,
        resource_file_out=args.resource_out,
        reset_when_done=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        help="YAML config file",
        type=str,
        required=True,
    )
    parser.add_argument(
        "-po",
        "--protocol_out",
        help="Path to save the protocol to",
        type=Path,
    )
    parser.add_argument(
        "-ri",
        "--resource_in",
        help="Path to existing resource file to update",
        type=Path,
    )
    parser.add_argument(
        "-ro",
        "--resource_out",
        help="Path to save the resource file to",
        type=Path,
    )

    args = parser.parse_args()
    main(args)
