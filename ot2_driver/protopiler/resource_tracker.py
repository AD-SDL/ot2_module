import json
from pathlib import Path
from typing import Optional, Union
from argparse import ArgumentParser

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


class ResourceTracker:
    def __init__(
        self,
        resource_file: Optional[Union[Path, str]] = None,
        labware_to_location: dict[str, str] = None,
        location_to_labware: dict[str, str] = None,
        pipette_to_mount: dict[str, str] = None,
        mount_to_pipette: dict[str, str] = None,
    ) -> None:

        self.labware_to_location = labware_to_location
        self.location_to_labware = location_to_labware
        self.pipette_to_mount = pipette_to_mount
        self.mount_to_pipette = mount_to_pipette

        if resource_file:
            self.resource_file = Path(resource_file)
            if resource_file.exists():
                self.resources = json.load(open(resource_file))

        elif labware_to_location:
            self.resources = self._create_resources()
        else:
            raise Exception("No existing resources or labware layout...")

    def _create_resources(self):
        # TODO: figure out how I want this to be handled
        # Should i plan to make this thing take in other
        # instances of things that need to be tracked?
        resources = {}
        if not self.labware_to_location:
            raise Exception("No information on labware found...")

        for name, location in self.labware_to_location.items():
            if isinstance(location, list):
                for loc in location:
                    if loc not in resources:
                        resources[loc] = {
                            "name": name,
                            "used": 0,
                            "depleted": False,
                        }
                    if (
                        "wellplate" in name and "wells_used" not in resources[loc]
                    ):  # adding the wellplate set tracker
                        resources[loc]["wells_used"] = set()
            else:
                if location not in resources:
                    resources[location] = {
                        "name": name,
                        "used": 0,
                        "depleted": False,
                    }
                if (
                    "wellplate" in name and "wells_used" not in resources[location]
                ):  # adding the wellplate set tracker
                    resources[location]["wells_used"] = set()

        return resources

    def get_available_tips(self):
        pass

    def get_used_tips(self):
        pass

    def get_next_tip(self):
        pass

    def get_used_wells(self):
        pass

    def get_available_wells(self):
        pass

    def get_next_well(self):
        pass

    """ Getters and setters for necesary info """

    def setup(
        self,
        labware_to_location: dict[str, str],
        location_to_labware: dict[str, str],
        pipette_to_mount: dict[str, str],
        mount_to_pipette: dict[str, str],
    ):
        # TODO: do None checks and verify overwriting things
        self.set_labware_to_location(labware_to_location)
        self.set_location_to_labware(location_to_labware)
        self.set_pipette_to_mount(pipette_to_mount)
        self.set_mount_to_pipette(mount_to_pipette)

    def set_labware_to_location(self, labware_to_location):
        self.labware_to_location = labware_to_location

    def set_location_to_labware(self, location_to_labware):
        self.location_to_labware = location_to_labware

    def set_pipette_to_mount(self, pipette_to_mount):
        self.pipette_to_mount = pipette_to_mount

    def set_mount_to_pipette(self, mount_to_pipette):
        self.mount_to_pipette = mount_to_pipette


def main(args):

    if args.resource_file:
        rf = ResourceTracker(resource_file=args.resource_file)
    else:
        labware_to_location = {
            "corning_96_wellplate_360ul_flat": "2",
            "corning_96_wellplate_360ul_flat": "3",
            "opentrons_96_tiprack_1000ul": "8",
        }
        location_to_labware = {v: k for k, v in labware_to_location.items()}
        pipette_to_mount = {"p1000_single_gen2": "right"}
        mount_to_pipette = {v: k for k, v in pipette_to_mount.items()}

        rf = ResourceTracker(
            labware_to_location=labware_to_location,
            location_to_labware=location_to_labware,
            pipette_to_mount=pipette_to_mount,
            mount_to_pipette=mount_to_pipette,
        )

    print(rf.resources)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "-rf", "--resource_file", type=Path, help="Path to json resources file"
    )

    args = parser.parse_args()
    main(args)
