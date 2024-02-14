"""Stores dataclasses/args/config for the ot2 drivers"""
import json
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Optional, Type, TypeVar, Union

import yaml
from pydantic import BaseModel as _BaseModel

_T = TypeVar("_T")

PathLike = Union[str, Path]


class BaseModel(_BaseModel):
    """Allows any sub-class to inherit methods allowing for programmatic description of protocols
    Can load a yaml into a class and write a class into a yaml file.
    """

    def dict(self, **kwargs):
        """Return the dictionary without the hidden fields
        Returns
        -------
        dict
            Dict representation of the object
        """
        hidden_fields = set(
            attribute_name
            for attribute_name, model_field in self.__fields__.items()
            if model_field.field_info.extra.get("hidden") is True
        )
        kwargs.setdefault("exclude", hidden_fields)
        return super().dict(**kwargs)

    def json(self, **kwargs) -> str:
        """Returns the json representation of the object without the hidden fields
        Returns
        -------
        str
            returns the JSON string of the object
        """
        hidden_fields = set(
            attribute_name
            for attribute_name, model_field in self.__fields__.items()
            if model_field.field_info.extra.get("hidden") is True
        )
        kwargs.setdefault("exclude", hidden_fields)
        return super().json(**kwargs)

    def write_yaml(self, cfg_path: PathLike) -> None:
        """Allows programmatic creation of ot2util objects and saving them into yaml.
        Parameters
        ----------
        cfg_path : PathLike
            Path to dump the yaml file.
        """
        with open(cfg_path, mode="w") as fp:
            yaml.dump(json.loads(self.json()), fp, indent=4, sort_keys=False)

    @classmethod
    def from_yaml(cls: Type[_T], filename: PathLike) -> _T:
        """Allows loading of yaml into ot2util objects.
        Parameters
        ----------
        filename: PathLike
            Path to yaml file location.
        """
        with open(filename) as fp:
            raw_data = yaml.safe_load(fp)
        return cls(**raw_data)  # type: ignore[call-arg]


class OT2_Config(BaseModel):
    """OT2 config dataclass."""

    ip: str
    port: int = 31950
    model: str = "OT2"
    version: Optional[int] = None


def parse_ot2_args() -> Namespace:
    """Parse command line args

    Returns
    -------
    Namespace
        A namespace of the arguments
    """
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
        "-po",
        "--protocol_out",
        type=Path,
        help="Optional, name/location for protocol file to be saved to",
    )
    parser.add_argument(
        "-ro",
        "--resource_out",
        type=Path,
        help="Optional, name/location for resources used file to be saved to",
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
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print status along the way"
    )
    parser.add_argument(
        "-ts",
        "--test_streaming",
        help="Option to test streaming line item commands",
        action="store_true",
    )

    return parser.parse_args()
