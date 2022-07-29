import json
import yaml
from pathlib import Path
from argparse import ArgumentParser
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


def parse_ot2_args():
    parser = ArgumentParser()
    parser.add_argument(
        "-rc",
        "--robot_config",
        type=Path,
        help="Path to config for OT2(s), must be present even if simulating, can contain dummy data however",
        required=True,
    )
    parser.add_argument(
        "-pc",
        "--protocol_config",
        type=Path,
        help="Path to protocol config or protocol.py",
        default=Path("./protopiler/example_configs/basic_config.yaml"),
    )
    parser.add_argument(
        "-rf",
        "--resource_file",
        type=Path,
        help="Path to resource file that currently exists",
    )
    parser.add_argument(
        "-po", "--protocol_out", type=Path, help="Optional, name/location for protocol file to be saved to"
    )
    parser.add_argument(
        "-ro", "--resource_out", type=Path, help="Optional, name/location for resources used file to be saved to"
    )
    parser.add_argument(
        "-s",
        "--simulate",
        default=False,
        action="store_true",
        help="Simulate the run, don't actually connect to the opentrons",
    )
    parser.add_argument(
        "-d",
        "--delete",
        action="store_true",
        help="Delete resource files and protocol files when done, default false",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print status along the way")

    return parser.parse_args()
