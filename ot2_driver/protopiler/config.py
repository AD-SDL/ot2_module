import json
import yaml
from pathlib import Path
from typing import TypeVar, Union, Type, Optional, List

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


# Resources
class Resource(BaseSettings):
    location: Path
    name: str


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


class ProtocolConfig(BaseSettings):
    resources: Optional[List[Resource]]
    equipment: List[Union[Labware, Pipette]]
    commands: List[Command]
    metadata: Metadata
