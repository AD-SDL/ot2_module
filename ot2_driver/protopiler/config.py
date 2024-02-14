"""Dataclasses and other configuration used in the protopiler"""
import json
from pathlib import Path
from typing import List, Optional, Type, TypeVar, Union

import yaml
from ..config import BaseModel

_T = TypeVar("_T")

PathLike = Union[str, Path]


# Resources
class Resource(BaseModel):
    """Wrapper for a file-based resource used in a configuration"""

    location: Path
    """The location to the file"""
    name: str
    """The name used to refer to the file in the configuration  """


# Labware containers
class Labware(BaseModel):
    """Container for a labware object, goes on the deck"""

    name: str
    """Name of the labware, should follow opentrons  naming standards"""
    location: str
    """String location of the labware on the deck, str representation of int [1-12]"""
    alias: Optional[str] = None
    """A nickname you can use to refer to this labware in the configuration"""
    module: Optional[str] = None
    """Name of labware that is attached to module in this deck position, should follow opentrons naming standards"""
    offset: Optional[List[float]] = None
    """Labware offset data to be imported for specific protocol"""


class Pipette(BaseModel):
    """Container for a pipette"""

    name: str
    """The name of this pipette, needs to follow opentrons naming scheme"""
    mount: str
    """Mount location, either left or right"""


class CommandBase(BaseModel):
    name: Optional[str] = None
    """Name of the command, optional"""


class Transfer(CommandBase):
    source: Union[List[str], str]
    """Source of the command, this should refer to a wellplate and well(s)"""
    aspirate_clearance: Optional[Union[List[float], float]] = 1
    """height of pipette when performing aspirate"""
    destination: Union[List[str], str]
    """Destination for the command, should refer to a wellplate and well(s)"""
    dispense_clearance: Optional[Union[float, List[float]]] = 1
    """height of pipette when performing dispense"""
    volume: Union[float, List[float], str]
    """Volume to transfer, can be a single int (microliters) or a list of int"""
    mix_cycles: Optional[Union[int, List[int]]] = 0
    """Num mixes"""
    mix_volume: Optional[Union[int, List[int]]] = 0
    """Volume of each mix"""
    blow_out: Optional[Union[bool, List[bool]]] = True
    """blow out from tip into current location"""
    drop_tip: Union[bool, List[bool]] = True
    """Drop the tip once a transfer is done"""
    return_tip: Union[bool, List[bool]] = False
    """puts tip back into tip box"""


class Multi_Transfer(CommandBase):
    multi_source: Union[str, List[List[str]]]
    """List of sources to be aspirated, each list within matrix presumed to be in single column"""
    multi_aspirate_clearance: Optional[Union[List[float], float]] = 1
    """height of pipette when performing aspirate"""
    multi_destination: Union[str, List[List[str]]]
    """List of sources to be aspirated, each list within matrix presumed to be in single column"""
    multi_dispense_clearance: Optional[Union[List[float], float]] = 1
    """height of pipette when performing aspirate"""
    multi_volume: Union[float, List[float], str]
    """volume to transfer (microliters)"""
    multi_mix_cycles: Optional[Union[int, List[int]]] = 0
    """Num mixes"""
    multi_mix_volume: Optional[Union[int, List[int]]] = 0
    """Volume of each mix"""
    multi_blow_out: Optional[Union[bool, List[bool]]] = True
    """blow out from tip into current location"""
    multi_drop_tip: Union[bool, List[bool]] = True
    """Drop the tip once a transfer is done"""


class Mix(CommandBase):
    reps: Union[int, List[int]]
    """how many mix cycles"""
    mix_volume: Union[float, List[float]]
    """volume to be mixed"""
    location: Union[List[str], str]
    """mixing destination"""


class Deactivate(CommandBase):
    deactivate: bool
    """Deactivates current module"""


class Temperature_Set(CommandBase):
    change_temp: int
    """Temperature to set temperature module to"""


class Replace_Tip(CommandBase):
    replace_tip: bool
    """Place tip back into tip rack"""


class Clear_Pipette(CommandBase):
    clear: bool
    """Blowout and remove any tip on pipette over trash"""


class Move_Pipette(CommandBase):
    move_to: int
    """Moves pipette to given deck position"""


# metadata container
class Metadata(BaseModel):
    """Container for the run metadata"""

    protocolName: Optional[str] = "NA"
    """Name to give to the protocol"""
    author: Optional[str] = "NA"
    """Author"""
    description: Optional[str] = "NA"
    """Description of the protocol, can be longer"""
    apiLevel: Optional[str] = "2.12"
    """Current api version of the Opentrons"""


class ProtocolConfig(BaseModel):
    """Final container, wraps up an entire protocol file"""

    resources: Optional[List[Resource]] = []
    """The additional resources (currently xls, xlsx files) to be used when compiling a protocol"""
    equipment: List[Union[Labware, Pipette]]
    """A list of the equipment you want to use on the OT2"""
    commands: List[
        Union[
            Transfer,
            Multi_Transfer,
            Mix,
            Deactivate,
            Temperature_Set,
            Replace_Tip,
            Clear_Pipette,
            Move_Pipette,
            CommandBase,
        ]
    ]
    """Commands to execute during run"""
    metadata: Metadata
    """Information about the run"""
