"""Dataclasses and other configuration used in the protopiler"""
from pathlib import Path
from typing import List, Literal, Optional, TypeVar, Union

from pydantic import ValidationError, field_validator, model_validator

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
    """Base class for all commands"""

    name: Optional[str] = None
    """Name of the command, optional"""


class Transfer(CommandBase):
    """The transfer command, used to move liquids from one place to another"""

    command: Literal["transfer"]
    """The command to execute, should be transfer for this class"""
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

    @field_validator("*")
    @classmethod
    def simplify_single_element_lists(cls, v: _T) -> _T:
        """Ensure that list fields are either single values or multi-element lists"""
        if isinstance(v, list):
            if len(v) == 1:
                return v[0]
        return v

    @model_validator(mode="after")
    def check_list_lengths_match(self) -> "Transfer":
        """Make sure that all list fields are the same length, if they are lists"""
        iter_len = 0
        listable_fields = [
            "volume",
            "source",
            "destination",
            "mix_cycles",
            "mix_volume",
            "aspirate_clearance",
            "dispense_clearance",
            "blow_out",
            "drop_tip",
            "return_tip",
        ]
        for field in listable_fields:
            if isinstance(getattr(self, field), list):
                if iter_len == 0:
                    iter_len = len(getattr(self, field))
                elif len(getattr(self, field)) != iter_len:
                    raise ValidationError(
                        "Multiple iterables of different lengths found, cannot determine dimension to iterate over"
                    )
        if iter_len > 0:
            for field in listable_fields:
                if not isinstance(getattr(self, field), list):
                    setattr(self, field, [getattr(self, field)] * iter_len)
        return self


class Multi_Transfer(CommandBase):
    """The multi_transfer command, used to move liquids from one place to another in a matrix format"""

    command: Literal["multi_transfer"]
    """The command to execute, should be multi_transfer for this class"""
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

    @field_validator("*")
    @classmethod
    def simplify_single_element_lists(cls, v: _T) -> _T:
        """Ensure that list fields are either single values or multi-element lists"""
        if isinstance(v, list):
            if len(v) == 1:
                return v[0]
        return v

    @model_validator(mode="after")
    def check_list_lengths_match(self) -> "Transfer":
        """Make sure that all list fields are the same length, if they are lists"""
        iter_len = 0
        listable_fields = [
            "multi_volume",
            "multi_source",
            "multi_destination",
            "multi_mix_cycles",
            "multi_mix_volume",
            "multi_aspirate_clearance",
            "multi_dispense_clearance",
            "multi_blow_out",
            "multi_drop_tip",
        ]
        for field in listable_fields:
            if isinstance(getattr(self, field), list):
                if iter_len == 0:
                    iter_len = len(getattr(self, field))
                elif len(getattr(self, field)) != iter_len:
                    raise ValidationError(
                        "Multiple iterables of different lengths found, cannot determine dimension to iterate over"
                    )
        if iter_len > 0:
            for field in listable_fields:
                if not isinstance(getattr(self, field), list):
                    setattr(self, field, [getattr(self, field)] * iter_len)
        return self

class Mix(CommandBase):
    """The mix command, used to mix liquids in a wellplate"""

    command: Literal["mix"]
    """The command to execute, should be mix for this class"""
    reps: Union[int, List[int]]
    """how many mix cycles"""
    mix_volume: Union[float, List[float]]
    """volume to be mixed"""
    location: Union[List[str], str]
    """mixing destination"""


class Deactivate(CommandBase):
    """The deactivate command, used to deactivate a module"""

    command: Literal["deactivate"]
    """The command to execute, should be deactivate for this class"""
    deactivate: bool
    """Deactivates current module"""


class Temperature_Set(CommandBase):
    """The temperature_set command, used to set the temperature of a temperature module"""

    command: Literal["temperature_set", "set_temperature"]
    """The command to execute, should be temperature_set or set_temperature for this class"""
    change_temp: int
    """Temperature to set temperature module to"""


class Replace_Tip(CommandBase):
    """The replace_tip command, used to replace a tip(s) into the tip rack"""

    command: Literal["replace_tip"]
    """The command to execute, should be replace_tip for this class"""
    replace_tip: bool
    """Place tip back into tip rack"""



class Clear_Pipette(CommandBase):
    """The clear_pipette command, used to clear the pipette(s) of any liquid and dispose of the tips in the trash"""

    command: Literal["clear_pipette"]
    """The command to execute, should be clear_pipette for this class"""


class Move_Pipette(CommandBase):
    """The move_pipette command, used to move the pipette to a specific deck position"""

    command: Literal["move_pipette"]
    """The command to execute, should be move_pipette for this class"""
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
        ]
    ]
    """Commands to execute during run"""
    metadata: Metadata
    """Information about the run"""
