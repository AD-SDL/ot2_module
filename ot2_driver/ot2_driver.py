import subprocess
from typing import Optional, Union
from pathlib import Path
import fabric
import yaml
from pydantic import BaseModel
from argparse import ArgumentParser
from protopiler.protopiler import ProtoPiler


class OT2_Config(BaseModel):
    ip: str
    ssh_key: str
    model: str = "OT2"
    version: Optional[int]


class OT2_Driver:
    def __init__(self, config: OT2_Config) -> None:
        self.config: OT2_Config = config
        self.protopiler: ProtoPiler = ProtoPiler(
            template_dir=Path(
                "/Users/kyle/github/ot2_driver/ot2_driver/protopiler/protocol_templates"
            )
        )

    def _connect(self):

        return fabric.Connection(
            host=self.config.ip,
            user="root",
            connect_kwargs={
                "key_filename": [self.config.ssh_key],
            },
        )

    def compile_protocol(self, config_path):
        self.protopiler.load_config(config_path=config_path)

        protocol_out_path = self.protopiler.yaml_to_protocol(config_path)

        return protocol_out_path

    def transfer(self, protocol_path: Union[Path, str], out_path: str = "/root"):
        cmd = ["scp", "-r", protocol_path, f"root@{self.config.ip}:{out_path}"]

        proc = subprocess.run(cmd)

        return proc.returncode

    def execute(self, remote_protcol_path: str):
        conn = self._connect()
        cmd = f"opentrons_execute {remote_protcol_path}"
        print(conn.run(cmd))


def main(args):
    ot2s = []
    for ot2_raw_cfg in yaml.safe_load(open(args.robot_config)):
        ot2s.append(OT2_Driver(OT2_Config(**ot2_raw_cfg)))

    ot2: OT2_Driver = ot2s[0]

    out_path = ot2.compile_protocol(args.protocol_config)
    returncode = ot2.transfer(out_path)

    if returncode:
        print("Exception raised when transferring")

    ot2.execute(out_path)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "-rc", "--robot_config", type=Path, help="Path to config for OT2(s)"
    )
    parser.add_argument(
        "-pc",
        "--protocol_config",
        type=Path,
        help="Path to protocol config or protocol.py",
        default=Path("./protopiler/example_configs/basic_config.yaml"),
    )

    args = parser.parse_args()
    main(args)
