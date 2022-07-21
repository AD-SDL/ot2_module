import re
import yaml
import json
from pathlib import Path
from copy import deepcopy
from datetime import datetime
from argparse import ArgumentParser
from typing import Optional, Dict, List

from protopiler.config import PathLike, Labware, Pipette

"""
Notes

TODO:
Design:
-------
    - should this class manage resources for more than one thing? Or just OT2?

Code:
-----
    - `create_resources` needs some TLC...
"""


class ResourceManager:
    def __init__(
        self,
        equiment_config: Optional[List[Dict[str, str]]] = None,
        resource_file: Optional[PathLike] = None,
    ) -> None:
        self.init = False

        if equiment_config:
            self.load_equipment(equipment_config=equiment_config, resource_file=resource_file)
            self.init = True

    def load_equipment(
        self,
        equipment_config: List[Dict[str, str]],
        resource_file: Optional[PathLike] = None,
    ) -> None:
        self.resource_file = resource_file

        # setup the necesary data relationships
        self._parse_equipment_config(equipment_config=equipment_config)

        # setup the resource tracker, if exists leave as is, else, create it
        resources = None
        try:
            self.resources
        except AttributeError:
            if resource_file:
                self.resource_file = Path(resource_file)
                if resource_file.exists():
                    resources = json.load(open(resource_file))

        self.resources = self._create_default_resources(resources=resources)

        self.init = True

    def _parse_equipment_config(self, equipment_config: List[Dict[str, str]]) -> None:
        labware = []
        pipettes = []

        for data in equipment_config:
            if isinstance(data, dict) and len(data) == 1:  # it is in form {"labware_type": {"key": "val" }}
                for _name, elem_data in data.items():
                    if "location" in elem_data.keys():
                        labware.append(Labware(**elem_data))
                    elif "mount" in elem_data.keys():
                        pipettes.append(Pipette(**elem_data))
            else:  # in form {"key": "val"}
                if "location" in data.keys():
                    labware.append(Labware(**data))
                elif "mount" in data.keys():
                    pipettes.append(Pipette(**data))

        # generate name -> location and location -> name relationships for labware
        self.labware_to_location = {}
        self.location_to_labware = {}
        self.alias_to_location = {}

        self.pipette_to_mount = {}
        self.mount_to_pipette = {}

        # generate labware -> location and location -> labware association
        for element in labware:
            if element.name in self.labware_to_location:
                self.labware_to_location[element.name].append(element.location)
            else:
                self.labware_to_location[element.name] = [element.location]

            if element.location in self.location_to_labware:
                raise Exception("Labware location overloaded, please check configuration")
            self.location_to_labware[element.location] = element.name

            if element.alias:
                self.alias_to_location[element.alias] = element.location

            # adding both the alias and the location just in case the user uses it interchangeably
            self.alias_to_location[element.location] = element.location

        for element in pipettes:
            # Generate pipette -> mount association
            if element.mount in self.mount_to_pipette:
                raise Exception("Pipette location overloaded, please check configuration")

            self.mount_to_pipette[element.mount] = element.name

            if element.name in self.pipette_to_mount:
                self.pipette_to_mount[element.name].append(element.mount)
            else:
                self.pipette_to_mount[element.name] = [element.mount]

    def _create_default_resources(self, resources: Optional[Dict] = None):
        # TODO: figure out how I want this to be handled
        # Should i plan to make this thing take in other
        # instances of things that need to be tracked?
        if not resources:
            resources = {}
        if not self.labware_to_location:
            raise Exception("No information on labware found...")

        for location, name in self.location_to_labware.items():
            if location not in resources:
                resources[location] = {
                    "name": name,
                    "used": 0,
                    "depleted": False,
                }
            # adding the wellplate set tracker
            if "wellplate" in name and "wells_used" not in resources[location]:
                resources[location]["wells_used"] = set()
            # if exists, convert it to set from list (set not serializable)
            if "wellplate" in name and "wells_used" in resources[location]:
                resources[location]["wells_used"] = set(resources[location]["wells_used"])

        return resources

    def get_available_tips(self, pipette_name) -> int:
        num_available = 0
        valid_tipracks_locations = self.find_valid_tipracks(pipette_name)

        for loc in valid_tipracks_locations:
            tiprack_name = self.location_to_labware[loc]
            # dependent on opentrons naming scheme
            capacity = int(tiprack_name.split("_")[1])
            left_in_tiprack = capacity - self.resources[loc]["used"]
            num_available += left_in_tiprack

        return num_available

    def get_used_tips(self, pipette_name) -> int:
        valid_tiprack_locations = self.find_valid_tipracks(pipette_name)

        num_used = 0
        for loc in valid_tiprack_locations:
            num_used += self.resources[loc]["used"]

        return num_used

    def get_next_tip(self, pipette_name) -> str:
        valid_tiprack_locations = self.find_valid_tipracks(pipette_name)
        for loc in valid_tiprack_locations:
            tiprack_name = self.location_to_labware[loc]
            # dependent on opentrons naming scheme
            capacity = int(tiprack_name.split("_")[1])
            # just in case someone manually messed with the json...
            if self.resources[loc]["used"] >= capacity:
                # data sanitization
                if not self.resources[loc]["depleted"]:
                    raise Exception("Resource data manipulation suspected... check resource file")

                continue

            # data sanitization
            if self.resources[loc]["depleted"]:
                raise Exception("Resource data manipulation suspected... check resource file")

            # leveraging the 0 indexing of the rack and the 1 indexing of the count
            # has to be a str because of the protocol writing
            next_tip = str(self.resources[loc]["used"])

            # update usage
            self.resources[loc]["used"] += 1
            if self.resources[loc]["used"] == capacity:
                self.resources[loc]["depleted"] = True

            return loc, next_tip

        raise Exception(f"Not enough tips found for '{pipette_name}'...")

    def update_tip_usage(self, pipette_name) -> None:
        valid_tiprack_locations = self.find_valid_tipracks(pipette_name)
        for loc in valid_tiprack_locations:
            tiprack_name = self.location_to_labware[loc]
            # dependent on opentrons naming scheme
            capacity = int(tiprack_name.split("_")[1])
            # just in case someone manually messed with the json...
            if self.resources[loc]["depleted"] or self.resources[loc]["used"] >= capacity:
                continue

            # update usage
            self.resources[loc]["used"] += 1
            if self.resources[loc]["used"] == capacity:
                self.resources[loc]["depleted"] = True

        raise Exception("No more tips found...")

    def update_well_usage(self, location: str, well: Optional[str] = None) -> None:
        if well:
            self.resources[location]["wells_used"].add(well)

            self.resources[location]["used"] = len(self.resources[location]["wells_used"])

        else:
            self.resources[location]["used"] += 1

        capacity = int(self.resources[location]["name"].split("_")[1])
        if self.resources[location]["used"] >= capacity:
            self.resources[location]["depleted"] = True

    def find_valid_tipracks(self, pipette_name: str) -> List[str]:
        """Finds the locations of valid tipracks for a given pipette, returned as list of strings

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
        pip_volume = int(pip_volume_pattern.search(pipette_name).group().replace("p", ""))
        valid_tipracks = []
        for labware_name, locations in self.labware_to_location.items():
            matches = rack_volume_pattern.search(labware_name)
            if matches is not None:
                vol = int(matches.group().replace("ul", ""))
                if vol == pip_volume:
                    for location in locations:
                        valid_tipracks.append(str(location))

        return valid_tipracks

    def determine_pipette(self, target_volume: int) -> str:
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

            # TODO: make sure the pipettes can handle the max they are labeled as
            if pip_volume >= target_volume:
                if pip_volume < min_available:
                    min_available = pip_volume
                    pipette = mount

        return pipette

    def dump_resource_json(self, out_file: Optional[PathLike] = None) -> str:
        out_resources = deepcopy(self.resources)
        for location in out_resources.keys():
            if "wells_used" in out_resources[location]:
                out_resources[location]["wells_used"] = list(out_resources[location]["wells_used"])

            # determine out_path,
            # `out_file` param takes priority, then `resouce_file` from class, then a auto_generated name
            if not out_file:
                if not self.resource_file:
                    name = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_resources.json"
                    out_path = Path("./") / name
                else:
                    out_path = self.resource_file
            else:
                out_path = out_file

        with open(out_path, "w") as f:
            json.dump(out_resources, f, indent=2)

        return str(out_path)


def main(args):
    equipment_config = yaml.safe_load(open(args.config))["equipment"]

    rf = ResourceManager(equiment_config=equipment_config, resource_file=args.resource_file)

    print(rf.resources)
    print(rf.get_next_tip("p1000_single_gen2"))

    print(rf.resources)
    print(rf.get_next_tip("p1000_single_gen2"))


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-rf", "--resource_file", type=Path, help="Path to json resources file")
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        required=True,
        help="Path to protocol yaml file, only for testing",
    )

    args = parser.parse_args()
    main(args)