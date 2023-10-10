"""Deconstructor, parses a protocol and turns it into a config"""
import re
import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, Optional

from ot2_driver.protopiler.config import (
    Command,
    Labware,
    Metadata,
    Pipette,
    ProtocolConfig,
)


class Deconstructor:
    """Pull apart a python protocol into a config"""

    def __init__(self, opentrons_simulate_bin: str = "opentrons_simulate") -> None:
        """Initialize protocol deconstructor

        Parameters
        ----------
        opentrons_simulate_bin : str, optional
            Path to the opentrons simulate program, by default "opentrons_simulate"
        """
        self.opentrons_simulate_bin = opentrons_simulate_bin

        # TODO: db? load from json? load from current api?
        self.commands_parsing_strategy = {
            "Picking up tip": self._parse_picking_up_tip,
            "Aspirating": self._parse_aspirating,
            "Dispensing": self._parse_dispensing,
            "Dropping tip": self._parse_dropping_tip,
        }

        self.commands = []
        self.resources = []

        self.opentrons_tiprack_pattern = re.compile("Opentrons.*µL")

    def deconstruct(
        self, protocol_path: Path, config_path: Optional[Path] = None
    ) -> Path:
        """Deconstruct a protocol.py file into a configuration.yml file

        Parameters
        ----------
        protocol_path : Path
            Path to the input protocol.py file
        config_path : Optional[Path], optional
            Path to the output config.yml file, by default None

        Returns
        -------
        Path
            Path to the saved config.yml file, will be created if not given
        """
        sim_command_commands = f"{self.opentrons_simulate_bin} {protocol_path}"
        simulation_res = subprocess.run(
            sim_command_commands.split(), capture_output=True, text=True
        )

        if simulation_res.returncode:
            print(f"Simulation failed with error: {simulation_res.stdout}")

        raw_commands = simulation_res.stdout.strip()
        liminal_commands = []
        for raw_command in raw_commands.split("\n"):
            liminal_commands.append(self._parse_raw_command(raw_command))

        self._get_commands(liminal_commands)
        self._get_labware(liminal_commands)

        # find the pipette tips
        sim_command_labware = f"{self.opentrons_simulate_bin} {protocol_path} -l info"
        simulation_labware_res = subprocess.run(
            sim_command_labware.split(), capture_output=True, text=True
        )

        if simulation_labware_res.returncode:
            raise Exception("Cannot run simulation with long info")

        for new_pipette in self._find_pipettes(simulation_labware_res.stdout):
            occupied = False
            for resource in self.resources:
                if (
                    isinstance(resource, Pipette)
                    and new_pipette.mount == resource.mount
                ):
                    if len(resource.name) == 0:
                        continue
                    occupied = True
            if not occupied and len(new_pipette.name) != 0:
                self.resources.append(new_pipette)

        # lastly setup metadata
        metadata = Metadata()

        # Now construct config
        protocol_config = ProtocolConfig(
            equipment=self.resources, commands=self.commands, metadata=metadata
        )
        protocol_config.dump_yaml(args.config_out)

    def _get_commands(self, liminal_commands):
        """
        Get the commands from the liminal commands
        """
        potential_command = None
        for command in liminal_commands:
            potential_command = self._parse_liminal_command(command, potential_command)
            if potential_command is not None:
                if (
                    potential_command.destination != "NA"
                    and potential_command.source != "NA"
                    and potential_command.volume != "NA"
                ):
                    self.commands.append(potential_command)
                    potential_command = None

    def _get_labware(self, liminal_commands):
        """
        Gets the labware from the commands and adds it to resources
        """
        resource_names = {}
        for command in liminal_commands:
            try:
                key = command["info"]["labware_name"]
                val = command["info"]["labware_location"]
                if key in resource_names:
                    resource_names[key].add(val)
                else:
                    resource_names[key] = set(val)
            except KeyError:
                pass

        for name, locations in resource_names.items():
            for loc in locations:
                self.resources.append(Labware(name=name, location=loc))

    def _parse_raw_command(self, command: str) -> Dict:
        # TODO remove brittle solution from parsing if possible
        for key, strategy in self.commands_parsing_strategy.items():
            if key in command:
                return strategy(raw_command=command)

        return {
            "command": command,
            "info": {"error": f"Not matching key for command: {command}"},
        }

    def _parse_picking_up_tip(self, raw_command: str) -> Dict:
        # going with brittle solution for now...
        command = raw_command.split()
        tip_location = command[4]
        labware_name = "_".join([elem.lower() for elem in command[6:12]])
        labware_name = labware_name.replace("tip_rack", "tiprack")
        labware_name = labware_name.replace("_µl", "ul")
        location = command[-1]

        return {
            "command": "pickup_tip",
            "info": {
                "tip_location": tip_location,
                "labware_name": labware_name,
                "labware_location": location,
            },
        }

    def _parse_aspirating(self, raw_command: str) -> Dict:
        command = raw_command.split()
        volume = float(command[1])
        well_location = command[4]
        labware_name = "_".join([elem.lower() for elem in command[6:13]])
        labware_name = labware_name.replace("well_plate", "wellplate")
        labware_name = labware_name.replace("_µl", "ul")
        labware_location = command[14]

        return {
            "command": "aspirate",
            "info": {
                "volume": volume,
                "well_location": well_location,
                "labware_name": labware_name,
                "labware_location": labware_location,
            },
        }

    def _parse_dispensing(self, raw_command: str) -> Dict:
        command = raw_command.split()
        volume = float(command[1])
        well_location = command[4]
        labware_name = "_".join([elem.lower() for elem in command[6:13]])
        labware_name = labware_name.replace("well_plate", "wellplate")
        labware_name = labware_name.replace("_µl", "ul")
        labware_location = command[14]

        return {
            "command": "dispense",
            "info": {
                "volume": volume,
                "well_location": well_location,
                "labware_name": labware_name,
                "labware_location": labware_location,
            },
        }

    def _parse_dropping_tip(self, raw_command: str) -> Dict:
        return {"command": "drop_tip", "info": {}}

    def _parse_liminal_command(
        self, liminal_command: dict, partial_command: Command = None
    ) -> Optional[Command]:
        if "pickup_tip" == liminal_command["command"]:
            return partial_command

        if "aspirate" == liminal_command["command"]:
            if partial_command is not None and partial_command.destination == "NA":
                raise Exception(
                    "Cannot aspirate more than once without dispense, error parsing protocol"
                )
            location = liminal_command["info"]["labware_location"]
            well_location = liminal_command["info"]["well_location"]
            volume = int(liminal_command["info"]["volume"])
            partial_command = Command(
                source=f"{location}:{well_location}", destination="NA", volume=volume
            )
            return partial_command

        if "dispense" == liminal_command["command"]:
            if partial_command is None:
                raise Exception(
                    "Cannot dispense without aspiration, error parsing protocol"
                )
            location = liminal_command["info"]["labware_location"]
            well_location = liminal_command["info"]["well_location"]
            volume = int(liminal_command["info"]["volume"])
            partial_command.destination = f"{location}:{well_location}"
            return partial_command

        # TODO: this method assumes drop tip is always true, think about how to correct that
        if "drop_tip" == liminal_command["command"]:
            return partial_command

        return None

    def _find_pipettes(self, simulation_out: str) -> Pipette:
        for line in simulation_out.split("\n"):
            if "Instruments found" in line:
                split_on_pipettes = line.split(",")
                for raw_pipette_string in split_on_pipettes:
                    mount = " ".join(raw_pipette_string.split(":")[:3])
                    name = raw_pipette_string.split(":")[-1]
                    name = "_".join(name.split()[:-1]).lower().replace("-channel", "")
                    if "LEFT" in mount:
                        mount = "left"
                    elif "RIGHT" in mount:
                        mount = "right"
                    yield Pipette(name=name, mount=mount)


def main(args):  # noqa: D103
    deconstructor = Deconstructor()

    deconstructor.deconstruct(protocol_path=args.protocol, config_path=args.config_out)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "-p", "--protocol", type=Path, help="Path to the input protocol", required=True
    )
    parser.add_argument(
        "-co", "--config_out", type=Path, help="Path to output config file"
    )
    parser.add_argument(
        "-os",
        "--opentrons_simulate",
        type=str,
        help="Path to the opentrons simulate program, optional",
    )

    args = parser.parse_args()
    main(args)
