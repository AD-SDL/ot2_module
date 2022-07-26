import yaml
import requests
import subprocess
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, Union
from argparse import ArgumentParser

from protopiler.protopiler import ProtoPiler


class OT2_Config(BaseModel):
    ip: str
    port: int = 31950
    model: str = "OT2"
    version: Optional[int]


"""
Useful Endpoints

    - {ip}:{port}/redoc - http documentation

 curl --header 'Opentrons-Version: *' -F files=@protocol_20220721-113432.py  http://169.254.170.12:31950/protocols
    - {"id": "b918b676-4ec4-4414-a317-88c35be878fc}
"""


class OT2_Driver:
    def __init__(self, config: OT2_Config) -> None:
        self.config: OT2_Config = config
        self.protopiler: ProtoPiler = ProtoPiler(
            template_dir=(Path(__file__).parent.resolve() / "protopiler/protocol_templates")
        )

    def compile_protocol(self, config_path, resource_file=None):
        pass

    def transfer(self, protocol_path: Union[Path, str], out_path: str = "/root"):
        pass

    def execute(self, remote_protcol_path: str):
        pass


def main(args):
    ot2s = []
    for ot2_raw_cfg in yaml.safe_load(open(args.robot_config)):
        ot2s.append(OT2_Driver(OT2_Config(**ot2_raw_cfg)))

    ot2: OT2_Driver = ot2s[0]

    protocol_file, resource_file = ot2.compile_protocol(
        config_path=args.protocol_config, resource_file=args.resource_file
    )
    if args.simulate:
        print("Beginning simulation")
        cmd = ["opentrons_simulate", protocol_file]
        subprocess.run(cmd)
        if args.delete:
            protocol_file.unlink()
            if not args.resource_file:
                resource_file.unlink()
    else:
        print("Beginning protocol")
        returncode = ot2.transfer(protocol_file)
        if returncode:
            print("Exception raised when transferring")

        ot2.execute(protocol_file)

        if args.delete:
            # TODO: add way to delete things from ot2
            pass


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-rc", "--robot_config", type=Path, help="Path to config for OT2(s)")
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

    args = parser.parse_args()
    main(args)
