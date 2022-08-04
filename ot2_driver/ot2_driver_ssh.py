import yaml
import fabric
import subprocess
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional


from protopiler.protopiler import ProtoPiler
from protopiler.config import PathLike, parse_ot2_args


class OT2_Config(BaseModel):
    ip: str
    ssh_key: str
    model: str = "OT2"
    version: Optional[int]


class OT2_Driver:
    def __init__(self, config: OT2_Config) -> None:
        self.config: OT2_Config = config
        self.protopiler: ProtoPiler = ProtoPiler(
            template_dir=(Path(__file__).parent.resolve() / "protopiler/protocol_templates")
        )

    def _connect(self) -> fabric.Connection:
        """Connect via fabric to the OT2

        Returns
        -------
        fabric.Connection
            The connection object with the OT2
        """
        return fabric.Connection(
            host=self.config.ip,
            user="root",
            connect_kwargs={
                "key_filename": [self.config.ssh_key],
            },
        )

    def compile_protocol(self, config_path, resource_file=None, protocol_out=None, resource_out=None):
        """Compile the protocols via protopiler

        Can skip this step if you already have a full protocol

        Parameters
        ----------
        config_path : PathLike
            path to the configuration file (the one with the ot2 commands )
        resource_file : PathLike, optional
            path to an existing resource file, by default None, will be created if None

        Returns
        -------
        Tuple: [str, str]
            path to the protocol file and resource file
        """
        self.protopiler.load_config(config_path=config_path, resource_file=resource_file)

        protocol_out_path, protocol_resource_file = self.protopiler.yaml_to_protocol(
            config_path, protocol_out=protocol_out, resource_file=resource_file, resource_file_out=resource_out
        )

        return protocol_out_path, protocol_resource_file

    def transfer(self, protocol_path: PathLike, out_path: str = "/root") -> None:
        """Transfer the file via scp to the robot

        Parameters
        ----------
        protocol_path : PathLike
            path to protocol path (locally)
        out_path : str, optional
            path to protocol on OT2, by default "/root"

        Returns
        -------
        int
            return code from scp command
        """
        cmd = ["scp", "-r", protocol_path, f"root@{self.config.ip}:{out_path}"]

        proc = subprocess.run(cmd)

        return proc.returncode

    def execute(self, remote_protcol_path: str):
        """Execute the protocol at a given path

        Parameters
        ----------
        remote_protcol_path : str
            the path to the protocol on the OT2, should have come from `transfer()`
        """
        conn = self._connect()
        cmd = f"opentrons_execute {remote_protcol_path}"
        print(conn.run(cmd))


def load_ot2_config(robot_config: PathLike) -> List[OT2_Driver]:
    ot2s = []
    for ot2_raw_cfg in yaml.safe_load(open(args.robot_config)):
        ot2s.append(OT2_Driver(OT2_Config(**ot2_raw_cfg)))

    return ot2s


def main(args):
    # returns list of ot2s, but we just have one
    ot2 = load_ot2_config(args.robot_config)[0]

    # if the extension is not py, compile it to a protocol.py
    if "py" not in str(args.protocol_config):
        if args.verbose:
            print("Configuration found, compiling")
        protocol_file, resource_file = ot2.compile_protocol(
            config_path=args.protocol_config,
            resource_file=args.resource_file,
            protocol_out=args.protocol_out,
            resource_out=args.resource_out,
        )
        if args.verbose:
            print(f"Compiled protocol file to: {protocol_file}, and resource file: {resource_file}")
    else:
        print("Existing protocol found")
        protocol_file = args.protocol_config
        resource_file = None

    if args.simulate:
        print("Beginning simulation")
        cmd = ["opentrons_simulate", protocol_file]
        subprocess.run(cmd)
        if args.delete:
            protocol_file.unlink()
            if not args.resource_file and resource_file:
                resource_file.unlink()
    else:
        if args.verbose:
            print("Beginning protocol")

        returncode = ot2.transfer(protocol_file)
        if returncode:
            print("Exception raised when transferring")

        ot2.execute(protocol_file)

        if args.delete:
            # TODO: add way to delete things from ot2
            pass


if __name__ == "__main__":
    args = parse_ot2_args()
    main(args)
