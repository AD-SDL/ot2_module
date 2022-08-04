"""Stores dataclasses/args/config for the ot2 drivers"""
from typing import Union
from pathlib import Path
from argparse import ArgumentParser, Namespace

PathLike = Union[str, Path]


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
