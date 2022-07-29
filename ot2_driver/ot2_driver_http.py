import yaml
import requests
import subprocess
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, Tuple, Dict

from protopiler.protopiler import ProtoPiler
from protopiler.config import PathLike, parse_ot2_args


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


# Creating a session
```
# Creating the session works
curl http://169.254.197.67:31950/sessions -X POST -H "accept: application/json" -H "Opentrons-Version: 2" -H "Content-Type: application/json" -d "{\"data\":{\"sessionType\":\"liveProtocol\"}}"

# Running a command does not:
curl http://169.254.197.67:31950/sessions/b6d87d51-264e-4dbb-979d-672b3cd815b8/commands/execute -X POST -H "accept: application/json" -H "Opentrons-Version: 2" -H "Content-Type: application/json" -d "{\"data\":{\"command\":\"calibration.deck.moveToPointThree\",\"data\":{}}}"
{"errors":[{"id":"UnexpectedError","title":"Unexpected Internal Error","detail":"NotImplementedError: Enable useProtocolEngine feature flag to use live HTTP protocols","meta":{"stacktrace":"Traceback (most recent call last):\n  File \"usr/lib/python3.7/site-packages/fastapi/routing.py\", line 227, in app\n  File \"usr/lib/python3.7/site-packages/fastapi/routing.py\", line 159, in run_endpoint_function\n  File \"usr/lib/python3.7/site-packages/robot_server/service/session/router.py\", line 139, in session_command_execute_handler\n  File \"usr/lib/python3.7/site-packages/robot_server/service/session/session_types/base_session.py\", line 70, in execute_command\n  File \"usr/lib/python3.7/site-packages/robot_server/service/session/session_types/live_protocol/command_executor.py\", line 21, in execute\nNotImplementedError: Enable useProtocolEngine feature flag to use live HTTP protocols"}}]}


# The /settings endpoint that allows us to enable settings 
# has discontinued the `useProtocolEngine` flag... 
# it looks like it was disabled in version 5.0.0 (we are on 6.0.0)
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

    def transfer(self, protocol_path: PathLike) -> Tuple[str, str]:
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
        # TODO: maybe replace with pathlib?
        with open(protocol_path, "rb") as f:
            protocol_file_bin = f.read()
        files = {"files": protocol_file_bin}
        headers = {"Opentrons-Version": "2"}

        # transfer the protocol
        transfer_resp = requests.post(url=transfer_url, files=files, headers=headers)
        protocol_id = transfer_resp.json()["data"]["id"]

        # create the run
        run_url = f"http://{self.config.ip}:31950/runs"
        run_json = {"data": {"protocolId": protocol_id}}
        run_resp = requests.post(url=run_url, headers=headers, json=run_json)

        run_id = run_resp.json()["data"]["id"]

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

        resp_data = ot2.execute(run_id)
        print(resp_data)

        if args.delete:
            # TODO: add way to delete things from ot2
            pass


if __name__ == "__main__":
    args = parse_ot2_args()
    main(args)
