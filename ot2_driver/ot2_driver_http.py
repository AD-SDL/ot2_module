"""Driver implemented using HTTP protocol supported by Opentrons"""
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests
import yaml
from pydantic import BaseModel

from ot2_driver.config import PathLike, parse_ot2_args
from ot2_driver.protopiler.protopiler import ProtoPiler


class OT2_Config(BaseModel):
    """OT2 config dataclass."""

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
(miniconda3) ❯ curl http://169.254.170.12:31950/sessions -X POST -H "accept: application/json" -H "Opentrons-Version: 2" -H "Content-Type: application/json" -d "{\"data\":{\"sessionType\":\"liveProtocol\"}}"

#Running a command does not
{"data":{"id":"4dd62cc2-7bad-4bcc-9aec-c3052289bb65","createdAt":"2022-08-01T16:27:45.551969+00:00","details":{},"sessionType":"liveProtocol","createParams":null},"links":{"self":{"href":"/sessions/4dd62cc2-7bad-4bcc-9aec-c3052289bb65","meta":null},"commandExecute":{"href":"/sessions/4dd62cc2-7bad-4bcc-9aec-c3052289bb65/commands/execute","meta":null},"sessions":{"href":"/sessions","meta":null},"sessionById":{"href":"/sessions/{sessionId}","meta":null}}}%
(miniconda3) 130 ❯ curl http://169.254.170.12:31950/sessions/4dd62cc2-7bad-4bcc-9aec-c3052289bb65/commands/execute -X POST -H "accept: application/json" -H "Opentrons-Version: 2" -H "Content-Type: application/json" -d "{\"data\":{\"command\":\"calibration.deck.moveToPointThree\",\"data\":{}}}"

{"errors":[{"id":"UnexpectedError","title":"Unexpected Internal Error","detail":"NotImplementedError: Enable useProtocolEngine feature flag to use live HTTP protocols","meta":{"stacktrace":"Traceback (most recent call last):\n  File \"usr/lib/python3.7/site-packages/fastapi/routing.py\", line 227, in app\n  File \"usr/lib/python3.7/site-packages/fastapi/routing.py\", line 159, in run_endpoint_function\n  File \"usr/lib/python3.7/site-packages/robot_server/service/session/router.py\", line 139, in session_command_execute_handler\n  File \"usr/lib/python3.7/site-packages/robot_server/service/session/session_types/base_session.py\", line 70, in execute_command\n  File \"usr/lib/python3.7/site-packages/robot_server/service/session/session_types/live_protocol/command_executor.py\", line 21, in execute\nNotImplementedError: Enable useProtocolEngine feature flag to use live HTTP protocols"}}]}%
# When I check the settings, useProtocolEnginge is not an option (appears to be removed sometime between opentrons v4 and now)
(miniconda3) ❯ curl http://169.254.170.12:31950/settings -H "accept: application/json" -H "Opentrons-Version: 2"                          ~

{"settings":[{"id":"shortFixedTrash","old_id":"short-fixed-trash","title":"Short (55mm) fixed trash","description":"Trash box is 55mm tall (rather than the 77mm default)","restart_required":false,"value":null},{"id":"deckCalibrationDots","old_id":"dots-deck-type","title":"Deck calibration to dots","description":"Perform deck calibration to dots rather than crosses, for robots that do not have crosses etched on the deck","restart_required":false,"value":null},{"id":"disableHomeOnBoot","old_id":"disable-home-on-boot","title":"Disable home on boot","description":"Prevent robot from homing motors on boot","restart_required":false,"value":null},{"id":"useOldAspirationFunctions","old_id":null,"title":"Use older aspirate behavior","description":"Aspirate with the less accurate volumetric calibrations that were used before version 3.7.0. Use this if you need consistency with pre-v3.7.0 results. This only affects GEN1 P10S, P10M, P50S, P50M, and P300S pipettes.","restart_required":false,"value":null},{"id":"enableDoorSafetySwitch","old_id":null,"title":"Enable robot door safety switch","description":"Automatically pause protocols when robot door opens. Opening the robot door during a run will pause your robot only after it has completed its current motion.","restart_required":false,"value":null},{"id":"disableLogAggregation","old_id":null,"title":"Disable Opentrons Log Collection","description":"Prevent the robot from sending its logs to Opentrons for analysis. Opentrons uses these logs to troubleshoot robot issues and spot error trends.","restart_required":false,"value":true},{"id":"disableFastProtocolUpload","old_id":null,"title":"Use older protocol analysis method","description":"Use an older, slower method of analyzing uploaded protocols. This changes how the OT-2 validates your protocol during the upload step, but does not affect how your protocol actually runs. Opentrons Support might ask you to change this setting if you encounter problems with the newer, faster protocol analysis method.","restart_required":false,"value":null},{"id":"enableOT3HardwareController","old_id":null,"title":"Enable experimental OT3 hardware controller","description":"Do not enable. This is an Opentrons-internal setting to test new hardware.","restart_required":true,"value":null},{"id":"enableHeaterShakerPAPI","old_id":null,"title":"Enable Heater-Shaker Python API support","description":"Do not enable. This is an Opentrons internal setting to test a new module.","restart_required":false,"value":null}],"links":{}}%
```
"""


class OT2_Driver:
    """Driver code for the OT2 utilizing the built in HTTP server."""

    def __init__(self, config: OT2_Config) -> None:
        """Initialize OT2 driver.

        Parameters
        ----------
        config : OT2_Config
            Dataclass of the ot2_config
        """
        self.config: OT2_Config = config
        self.protopiler: ProtoPiler = ProtoPiler(
            template_dir=(Path(__file__).parent.resolve() / "protopiler/protocol_templates")
        )

    def compile_protocol(self, config_path, resource_file=None) -> Tuple[str, str]:
        """Compile the protocols via protopiler

        This step will be skipped if a full protocol file is detected

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
        if ".py" not in str(config_path):
            self.protopiler.load_config(config_path=config_path, resource_file=resource_file)

            protocol_out_path, protocol_resource_file = self.protopiler.yaml_to_protocol(
                config_path, resource_file=resource_file
            )

            return protocol_out_path, protocol_resource_file
        else:
            return config_path, None

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
        files = {"files": open(protocol_path, "rb")}
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

    def stream(
        self,
        command: str,
        params: dict,
        run_id: str = None,
        execute: bool = True,
        intent: str = "setup",
    ) -> str:
        """Wrapper for streaming individual commands to the OT2

        Parameters
        ----------
        command : str
            command type, to be executed on the OT2
        params : dict
            The arguments of the command, must follow api rules
        run_id : str, optional
            The run id to add this command to, by default will create a new run on the OT2, by default None
        execute : bool, optional
            Whether to execute the command now, or postpone execution of the run to later, by default True
        intent : str, optional
            either `protocol` or `setup`, whether the command should be executed immediately, or one a play action, by default "setup"

        Returns
        -------
        str
            The run id that was either given or created
        """

        return self._stream(command, params, run_id, execute=execute, intent=intent)

    def _stream(self, command, params, run_id=None, execute=True, intent="setup"):
        """Helper method that runs the streaming

                Parameters
        ----------
        command : str
            command type, to be executed on the OT2
        params : dict
            The arguments of the command, must follow api rules
        run_id : str, optional
            The run id to add this command to, by default will create a new run on the OT2, by default None
        execute : bool, optional
            Whether to execute the command now, or postpone execution of the run to later, by default True
        intent : str, optional
            either `protocol` or `setup`, whether the command should be executed immediately, or one a play action, by default "setup"

        Returns
        -------
        str
            The run id that was either given or created
        """
        headers = {"Opentrons-Version": "2"}

        if not run_id:
            # create a run
            run_resp = requests.post(
                url=f"http://{self.config.ip}:31950/runs",
                headers=headers,
                json={"data": {}},
            )
            run_id = run_resp.json()["data"]["id"]

        # queue the command
        enqueue_payload = {"data": {"commandType": command, "params": params, "intent": intent}}
        enqueue_resp = requests.post(
            url=f"http://{self.config.ip}:31950/runs/{run_id}/commands",
            headers=headers,
            json=enqueue_payload,
        )
        print(f"Enqueue return: {enqueue_resp.json()}")

        # run the command
        if execute:
            execute_command_resp = requests.post(
                url=f"http://{self.config.ip}:31950/runs/{run_id}/actions",
                headers=headers,
                json={"data": {"actionType": "play"}},
            )
            print(f"Execute return: {execute_command_resp.json()}")

        return run_id


def _test_streaming(ot2: OT2_Driver):
    run_id = ot2.stream(
        command="loadLabware",
        params={
            "location": {"slotName": "1"},
            "loadName": "corning_96_wellplate_360ul_flat",
            "namespace": "opentrons",
            "version": "1",
            "labwareId": "wellplate_1",
        },
        execute=False,
        intent="setup",
    )
    print()
    print()

    ot2.stream(
        command="loadLabware",
        params={
            "location": {"slotName": "2"},
            "loadName": "opentrons_96_tiprack_300ul",
            "namespace": "opentrons",
            "version": "1",
            # "labwareId": "tiprack_1",
        },
        run_id=run_id,
        execute=False,
        intent="setup",
    )
    print()
    print()

    ot2.stream(
        command="loadPipette",
        params={
            "pipetteName": "p300_multi_gen2",
            "mount": "right",
            "pipetteId": "p300_right",
        },
        run_id=run_id,
        execute=False,
        intent="setup",
    )
    print()
    print()

    ot2.stream(
        command="moveRelative",
        params={"pipetteId": "p300_right", "axis": "x", "distance": "-100"},
        run_id=run_id,
        execute=False,
    )
    ot2.stream(
        command="moveRelative",
        params={"pipetteId": "p300_right", "axis": "x", "distance": "-200"},
        run_id=run_id,
        execute=True,
    )

    exit()


def main(args):  # noqa: D103
    ot2s = []
    for ot2_raw_cfg in yaml.safe_load(open(args.robot_config)):
        ot2s.append(OT2_Driver(OT2_Config(**ot2_raw_cfg)))

    ot2: OT2_Driver = ot2s[0]

    # testing streaming
    if args.test_streaming:
        _test_streaming(ot2)

    # Can pass in a full python file here, no resource files will be created, but it won't break the system
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
        print(f"Protocol execution response data: {resp_data}")

        if args.delete:
            # TODO: add way to delete things from ot2
            pass


if __name__ == "__main__":
    args = parse_ot2_args()
    main(args)
