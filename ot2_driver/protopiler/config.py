"""Dataclasses and other configuration used in the protopiler"""
import json
from pathlib import Path
from typing import List, Optional, Type, TypeVar, Union

import yaml
from pydantic import BaseSettings as _BaseSettings

_T = TypeVar("_T")

PathLike = Union[str, Path]


class BaseSettings(_BaseSettings):
    """Overiding the pydantic base settings to allow for reading from yaml

    Parameters
    ----------
    _BaseSettings
        Pydantic base settings
    """

    def dump_yaml(self, cfg_path: PathLike) -> None:
        """Allows for saving of pydantic objects to yaml files

        Parameters
        ----------
        cfg_path : PathLike
            path to save the file
        """
        with open(cfg_path, mode="w") as fp:
            yaml.dump(json.loads(self.json()), fp, indent=4, sort_keys=False)

    @classmethod
    def from_yaml(cls: Type[_T], filename: PathLike) -> _T:
        """Allows models to be loaded from a path to yaml file

        Parameters
        ----------
        cls : Type[_T]

        filename : PathLike
            path to the yaml file

        Returns
        -------
        _T
        """
        with open(filename) as fp:
            raw_data = yaml.safe_load(fp)
        return cls(**raw_data)  # type: ignore[call-arg]


# Resources
class Resource(BaseSettings):
    """Wrapper for a file-based resource used in a configuration"""

    location: Path
    """The location to the file"""
    name: str
    """The name used to refer to the file in the configuration  """


# Labware containers
class Labware(BaseSettings):
    """Container for a labware object, goes on the deck"""

    name: str
    """Name of the labware, should follow opentrons  naming standards"""
    location: str
    """String location of the labware on the deck, str representation of int [1-12]"""
    alias: Optional[str]
    """A nickname you can use to refer to this labware in the configuration"""
    module: Optional[str]
    """Name of labware that is attached to module in this deck position, should follow opentrons naming standards"""
    offset: Optional[List[float]]
    """Labware offset data to be imported for specific protocol"""


class Pipette(BaseSettings):
    """Container for a pipette"""

    name: str
    """The name of this pipette, needs to follow opentrons naming scheme"""
    mount: str
    """Mount location, either left or right"""


class CommandBase(BaseSettings):
    name: Optional[str]
    """Name of the command, optional"""


class Transfer(CommandBase):
    source: Union[List[str], str]
    """Source of the command, this should refer to a wellplate and well(s)"""
    aspirate_clearance: Optional[Union[List[float], float]]
    """height of pipette when performing aspirate"""
    destination: Union[List[str], str]
    """Destination for the command, should refer to a wellplate and well(s)"""
    dispense_clearance: Optional[Union[float, List[float]]]
    """height of pipette when performing dispense"""
    volume: Union[float, List[float], str]
    """Volume to transfer, can be a single int (microliters) or a list of int"""
    mix_cycles: Optional[Union[int, List[int]]]
    """Num mixes"""
    mix_volume: Optional[Union[int, List[int]]]
    """Volume of each mix"""
    blow_out: Optional[Union[bool, List[bool]]] = True
    """blow out from tip into current location"""
    drop_tip: Union[bool, List[bool]] = True
    """Drop the tip once a transfer is done"""

class Temperature_Set(CommandBase):
    change_temp: int
    """Temperature to set temperature module to"""

class Clear_Pipette(CommandBase):
    clear: bool
    """Blowout and remove any tip on pipette over trash"""

class Move_Pipette(CommandBase):
    move_to: int
    """Moves pipette to given deck position"""

# metadata container
class Metadata(BaseSettings):
    """Container for the run metadata"""

    protocolName: Optional[str] = "NA"
    """Name to give to the protocol"""
    author: Optional[str] = "NA"
    """Author"""
    description: Optional[str] = "NA"
    """Description of the protocol, can be longer"""
    apiLevel: Optional[str] = "2.12"
    """Current api version of the Opentrons"""


class ProtocolConfig(BaseSettings):
    """Final container, wraps up an entire protocol file"""

    resources: Optional[List[Resource]]
    """The additional resources (currently xls, xlsx files) to be used when compiling a protocol"""
    equipment: List[Union[Labware, Pipette]]
    """A list of the equipment you want to use on the OT2"""
    commands: List[Union[Transfer, Temperature_Set, Clear_Pipette, Move_Pipette, CommandBase]]
    """Commands to execute during run"""
    metadata: Metadata
    """Information about the run"""