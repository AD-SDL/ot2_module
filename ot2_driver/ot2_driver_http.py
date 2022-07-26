import yaml
import requests
import subprocess
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, Tuple, Union, Dict
from argparse import ArgumentParser

from protopiler.protopiler import ProtoPiler


class OT2_Config(BaseModel):
    ip: str
    port: int = 31950
    model: str = "OT2"
    version: Optional[int]


"""
Running example from REPL
```
    >>> import requests
    >>> robot_ip_address = "169.254.197.67"
    >>> upload_resp = requests.post(url=f"http://{robot_ip_address}:31950/protocols", files={'files': open('test_protocol.py', 'rb')}, headers={"Opentrons-Version": "2"})
    >>> run_resp = requests.post(url=f"http://{robot_ip_address}:31950/runs", headers={"Opentrons-Version": "2"}, json={"data": {"protocolId": upload_resp.json()['data']['id']}})
    >>> upload_resp.json()['data']['id']
    'dc3e49dd-15ba-444c-b7d7-4b2b26c53938'
    >>> run_resp.json()
    {'data': {'id': '0de315c8-a2d0-46c0-9df6-12ed88848321', 'createdAt': '2022-07-25T18:51:51.987747+00:00', 'status': 'idle', 'current': True, 'actions': [], 'errors': [], 'pipettes': [], 'modules': [], 'labware': [{'id': 'fixedTrash', 'loadName': 'opentrons_1_trash_1100ml_fixed', 'definitionUri': 'opentrons/opentrons_1_trash_1100ml_fixed/1', 'location': {'slotName': '12'}}], 'labwareOffsets': [], 'protocolId': 'dc3e49dd-15ba-444c-b7d7-4b2b26c53938'}}
    >>> run_id = run_resp.json()['data']['id']
    >>> executre_run_resp = requests.post(url=f"http://{robot_ip_address}:31950/runs/{run_id}", headers={"Opentrons-Version": "2"}, json={"data": {"actionType": "play"}})
    >>> executre_run_resp.json()
    {'errors': [{'id': 'BadRequest', 'title': 'Bad Request', 'detail': 'Method Not Allowed'}]}
    >>> execute_run_resp = requests.post(url=f"http://{robot_ip_address}:31950/runs/{run_id}/actions", headers={"Opentrons-Version": "2"}, json={"data": {"actionType": "play"}})
    >>> execute_run_resp.json()
    {'data': {'id': '7c43d567-6e09-4d01-b8ac-e7e03cc807de', 'createdAt': '2022-07-25T18:54:09.529435+00:00', 'actionType': 'play'}}
```
"""


class OT2_Driver:
    def __init__(self, config: OT2_Config) -> None:
        self.config: OT2_Config = config
        self.protopiler: ProtoPiler = ProtoPiler(
            template_dir=(Path(__file__).parent.resolve() / "protopiler/protocol_templates")
        )

    def compile_protocol(self, config_path, resource_file=None) -> Tuple[str, str]:
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
            config_path, resource_file=resource_file
        )

        return protocol_out_path, protocol_resource_file

    def transfer(self, protocol_path: Union[Path, str]) -> Tuple[str, str]:
        """Transfer the protocol file to the OT2 via http

        Parameters
        ----------
        protocol_path : Union[Path, str]
            path to the protocol file, locally

        Returns
        -------
        Tuple[str, str]
            returns `protocol_id`, and `run_id` in that order
        """
        transfer_url = f"http://{self.config.ip}:31950/protocols"
        files = {"files": open(protocol_path, "rb")}
        headers = {"Opentrons-Version": "2"}

        # transfer the protocol
        transfer_resp = requests.post(url=transfer_url, files=files, headers=headers)
        protocol_id = transfer_resp.json()["data"]["id"]

        # create the run
        run_url = f"http://{self.config.ip}:31950/runs"
        run_json = {"data": {"protocolId": protocol_id}}
        run_resp = requests.post(url=run_url, headers=headers, json=run_json)

        run_id = run_resp["data"]["id"]

        return protocol_id, run_id

    def execute(self, run_id: str) -> Dict[str, Dict[str, str]]:
        """Execute a `play` command for a given protocol-id

        Parameters
        ----------
        run_id : str
            the run ID coming from `transfer()`

        Returns
        -------
        Dict[str, Dict[str, str]]
            the json response from the OT2 execute command
        """
        execute_url = f"http://{self.config.ip}:31950/runs/{run_id}/actions"
        headers = {"Opentrons-Version": "2"}
        execute_json = {"data": {"actionType": "play"}}

        execute_run_resp = requests.post(url=execute_url, headers=headers, json=execute_json)

        return execute_run_resp.json()


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
        protocol_id, run_id = ot2.transfer(protocol_file)

        ot2.execute(run_id)

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
