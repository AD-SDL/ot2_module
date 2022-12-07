"""Driver implemented using HTTP protocol supported by Opentrons"""
import subprocess
import time
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import requests
import yaml
from urllib3 import Retry

from ot2_driver.config import PathLike, parse_ot2_args, OT2_Config
from ot2_driver.protopiler.protopiler import ProtoPiler


class RobotStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"


class RunStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    FINISHING = "finishing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class OT2_Driver:
    """Driver code for the OT2 utilizing the built in HTTP server."""

    def __init__(
        self,
        config: OT2_Config,
        retries: int = 5,
        retry_backoff: float = 1.0,
        retry_status_codes: Optional[List[int]] = None,
    ) -> None:
        """Initialize OT2 driver.

        Parameters
        ----------
        config : OT2_Config
            Dataclass of the ot2_config
        """
        self.config: OT2_Config = config
        template_dir = Path(__file__).parent.resolve() / "protopiler/protocol_templates"
        assert template_dir.exists(), f"Template dir: {template_dir} does not exist"
        self.protopiler: ProtoPiler = ProtoPiler(template_dir=template_dir)

        self.retry_strategy = Retry(
            total=retries,
            backoff_factor=retry_backoff,
            status_forcelist=retry_status_codes,
        )

        # Test connection
        self.base_url = f"http://{self.config.ip}:{self.config.port}"
        self.headers = {"Opentrons-Version": "2"}
        test_conn_url = f"{self.base_url}/calibration/status"

        resp = requests.get(test_conn_url, headers=self.headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Could not connect to opentrons with config {config}")

    def compile_protocol(
        self, config_path, resource_file=None, payload: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
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
            self.protopiler.load_config(
                config_path=config_path, resource_file=resource_file
            )

            (
                protocol_out_path,
                protocol_resource_file,
            ) = self.protopiler.yaml_to_protocol(
                config_path, resource_file=resource_file, payload=payload
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
        # Make sure its a path object
        protocol_path = Path(protocol_path)

        transfer_url = f"{self.base_url}/protocols"
        files = {"files": protocol_path.open("rb")}

        # transfer the protocol
        transfer_resp = requests.post(
            url=transfer_url, files=files, headers=self.headers
        )
        protocol_id = transfer_resp.json()["data"]["id"]

        # create the run
        run_url = f"{self.base_url}/runs"
        run_json = {"data": {"protocolId": protocol_id}}
        run_resp = requests.post(url=run_url, headers=self.headers, json=run_json)

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
        execute_url = f"{self.base_url}/runs/{run_id}/actions"
        execute_json = {"data": {"actionType": "play"}}

        # TODO: do some error checking/handling on execute
        execute_run_resp = requests.post(
            url=execute_url, headers=self.headers, json=execute_json
        )
        if (
            execute_run_resp.status_code != 201
        ):  # this is the good respcode for this endpoint
            print(f"Could not run play action on {run_id}")
            print(execute_run_resp.json())

        while self.check_run_status(run_id) not in {
            RunStatus.FAILED,
            RunStatus.SUCCEEDED,
        }:
            time.sleep(1)

        return self.get_run(run_id)

    def check_run_status(self, run_id) -> RunStatus:
        """Checks the status of a run

        Parameters
        ----------
        run_id : str
            The run id, given by the opentrons API

        Returns
        -------
        RunStatus
            A enum of the current run status as reported by the ot2 (IDLE, RUNNING, FINISHING, FAILED, SUCCEEDED)
        """
        # check run
        check_run_url = f"{self.base_url}/runs/{run_id}"
        check_run_resp = requests.get(url=check_run_url, headers=self.headers)

        if check_run_resp.status_code != 200:
            print(f"Cannot check run {run_id}")
        status = RunStatus(check_run_resp.json()["data"]["status"])

        return status

    def get_run(self, run_id) -> Dict:
        """Get the OT2 summary of a specific run

        Parameters
        ----------
        run_id : str
            The run id given by the OT2 api

        Returns
        -------
        Dict
            The response json dictionary
        """
        run_url = f"{self.base_url}/runs/{run_id}"
        run_resp = requests.get(url=run_url, headers=self.headers)

        if run_resp.status_code != 200:
            print(f"Could not get run {run_id}")

        return run_resp.json()

    def get_runs(self) -> Optional[List[Dict[str, str]]]:
        """Get all the runs currently stored on the ot2

        Returns
        -------
        Optional[List[Dict[str, str]]]
            Returns a list of dictionaries that contain simplified information about the runs
        """
        runs_url = f"{self.base_url}/runs"
        runs_resp = requests.get(url=runs_url, headers=self.headers)

        if runs_resp.status_code == 200:
            runs_simplified = []
            for run in runs_resp.json()["data"]:
                runs_simplified.append(
                    {
                        "runID": run["id"],
                        "protocolID": run["protocolId"],
                        "status": run["status"],
                    }
                )

            return runs_simplified

        return None

    def get_robot_status(self) -> RobotStatus:
        """Return the status of the robot currently.

        Returns
        -------
        Status
            Either IDLE or RUNNING
        """
        for run in self.get_runs():
            if run["status"] == RobotStatus.RUNNING.value:
                return RobotStatus.RUNNING

        return RobotStatus.IDLE

    def send_request(self, request_extension: str, **kwargs) -> requests.Response:
        """Allows us to send arbitrary requests to the ot2 http server.

        Parameters
        ----------
        request_extension : str
            The extension (following the ip:port/) of the url we are requesting

        Returns
        -------
        requests.Request
            The request object returned from the OT2

        Raises
        ------
        Exception
            If there is no `method` keyword argument, This method does not specify the http request method, user must provide as keyword argument
        """
        # sanitize preceeding '/'
        request_extension = (
            request_extension if "/" != request_extension[0] else request_extension[1:]
        )
        url = f"{self.base_url}/{request_extension}"

        # check for headers
        if "headers" not in kwargs:
            kwargs["headers"] = {"Opentrons-Version": "2"}

        if "method" not in kwargs:
            raise Exception(
                "No request method specified, please provide GET, POST, UPDATE, DELETE as keyword argument"
            )
        else:
            kwargs["method"] = kwargs["method"].upper()

        return requests.request(url=url, **kwargs)

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

        if not run_id:
            # create a run
            run_resp = requests.post(
                url=f"{self.base_url}/runs",
                headers=self.headers,
                json={"data": {}},
                max_retries=self.retry_strategy,
            )
            run_id = run_resp.json()["data"]["id"]

        # queue the command
        enqueue_payload = {
            "data": {"commandType": command, "params": params, "intent": intent}
        }
        enqueue_resp = requests.post(
            url=f"{self.base_url}/runs/{run_id}/commands",
            headers=self.headers,
            json=enqueue_payload,
            max_retries=self.retry_strategy,
        )
        print(f"Enqueue return: {enqueue_resp.json()}")

        # run the command
        if execute:
            execute_command_resp = requests.post(
                url=f"{self.base_url}/runs/{run_id}/actions",
                headers=self.headers,
                json={"data": {"actionType": "play"}},
                max_retries=self.retry_strategy,
            )
            print(f"Execute return: {execute_command_resp.json()}")

        return run_id


def main(args):  # noqa: D103
    ot2s = []
    for ot2_raw_cfg in yaml.safe_load(open(args.robot_config)):
        ot2s.append(OT2_Driver(OT2_Config(**ot2_raw_cfg)))

    ot2: OT2_Driver = ot2s[0]

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
