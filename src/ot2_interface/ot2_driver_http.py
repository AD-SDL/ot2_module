"""Driver implemented using HTTP protocol supported by Opentrons"""

import time
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import requests
from madsci.common.types.base_types import PathLike
from urllib3 import Retry


class RobotStatus(Enum):
    """status of ot2"""

    IDLE = "idle"
    RUNNING = "running"
    FINISHING = "finishing"
    FAILED = "failed"
    PAUSED = "paused"
    OFFLINE = "offline"


class RunStatus(Enum):
    """status of run on ot2"""

    IDLE = "idle"
    RUNNING = "running"
    FINISHING = "finishing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PAUSED = "paused"
    STOPPING = "stop-requested"
    STOPPED = "stopped"


class OpentronsInterface:
    """Driver code for the OT2 utilizing the built in HTTP server."""

    def __init__(
        self,
        ot2_ip: str,
        ot2_port: int = 31950,
        retries: int = 5,
        retry_backoff: float = 1.0,
        retry_status_codes: Optional[list[int]] = None,
    ) -> None:
        """Initialize OT2 driver.

        Parameters
        ----------
        config : OT2_Config
            Dataclass of the ot2_config
        """
        self.retry_strategy = Retry(
            total=retries,
            backoff_factor=retry_backoff,
            status_forcelist=retry_status_codes,
        )

        # Test connection
        self.base_url = f"http://{ot2_ip}:{ot2_port}"
        self.headers = {"Opentrons-Version": "2"}
        test_conn_url = f"{self.base_url}/robot/lights"

        resp = requests.get(test_conn_url, headers=self.headers, timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Could not connect to opentrons with url {self.base_url}"
            )

        if "on" in resp.json() and not resp.json()["on"]:
            self.change_lights_status(status=True)
        else:
            self.change_lights_status(status=False)
            time.sleep(1)  # Can mix later
            self.change_lights_status(status=True)

    def transfer(self, protocol_path: PathLike) -> tuple[str, str]:
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
            url=transfer_url, files=files, headers=self.headers, timeout=10
        )
        protocol_id = transfer_resp.json()["data"]["id"]

        # create the run
        run_url = f"{self.base_url}/runs"
        run_json = {"data": {"protocolId": protocol_id}}
        run_resp = requests.post(
            url=run_url, headers=self.headers, json=run_json, timeout=10
        )

        run_id = run_resp.json()["data"]["id"]

        return protocol_id, run_id

    def execute(self, run_id: str) -> dict[str, dict[str, str]]:
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
            url=execute_url, headers=self.headers, json=execute_json, timeout=10
        )
        if (
            execute_run_resp.status_code != 201
        ):  # this is the good response code for this endpoint
            pass

        while True:
            try:
                if self.check_run_status(run_id) in {
                    RunStatus.FAILED,
                    RunStatus.SUCCEEDED,
                    RunStatus.STOPPED,
                }:
                    break
                time.sleep(1)

            except Exception as e:
                self.logger.log_error(
                    f"Error while checking run status: {e}, continuing to wait for run to finish"
                )

        return self.get_run(run_id)

    def pause(self, run_id: str) -> dict[str, dict[str, str]]:
        """Execute a `pause` command for a given protocol-id

        Parameters
        ----------
        run_id : str
            the run ID coming from `transfer()`

        Returns
        -------
        Dict[str, Dict[str, str]]
            the json response from the OT2 pause command
        """
        execute_url = f"{self.base_url}/runs/{run_id}/actions"
        execute_json = {"data": {"actionType": "pause"}}

        # TODO: do some error checking/handling on execute
        return requests.post(
            url=execute_url, headers=self.headers, json=execute_json, timeout=10
        )

    def resume(self, run_id: str) -> dict[str, dict[str, str]]:
        """Execute a `play` command for a given protocol-id

        Parameters
        ----------
        run_id : str
            the run ID coming from `transfer()`

        Returns
        -------
        Dict[str, Dict[str, str]]
            the json response from the OT2 play command
        """
        execute_url = f"{self.base_url}/runs/{run_id}/actions"
        execute_json = {"data": {"actionType": "play"}}

        # TODO: do some error checking/handling on execute
        return requests.post(
            url=execute_url, headers=self.headers, json=execute_json, timeout=10
        )

    def cancel(self, run_id: str) -> dict[str, dict[str, str]]:
        """Execute a `stop` command for a given protocol-id

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
        execute_json = {"data": {"actionType": "stop"}}

        # TODO: do some error checking/handling on execute
        return requests.post(
            url=execute_url, headers=self.headers, json=execute_json, timeout=10
        )

    def check_run_status(self, run_id: str) -> RunStatus:
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
        check_run_resp = requests.get(
            url=check_run_url, headers=self.headers, timeout=10
        )

        return RunStatus(check_run_resp.json()["data"]["status"])

    def get_run(self, run_id: str) -> dict:
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
        run_resp = requests.get(url=run_url, headers=self.headers, timeout=10)

        if run_resp.status_code != 200:
            pass

        return run_resp.json()

    def get_run_log(self, run_id: str) -> dict:
        """Get the OT2 summary of a specific run, with commands

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
        run_resp = requests.get(
            url=run_url,
            headers=self.headers,
            params={"cursor": 0, "pageLength": 1000},
            timeout=10,
        )

        if run_resp.status_code != 200:
            pass

        commands_url = f"{self.base_url}/runs/{run_id}/commands"
        commands_resp = requests.get(
            url=commands_url,
            headers=self.headers,
            params={"cursor": 0, "pageLength": 1000},
            timeout=10,
        )

        if commands_resp.status_code != 200:
            pass

        result = run_resp.json()
        result["commands"] = commands_resp.json()

        return result

    def get_runs(self) -> Optional[list[dict[str, str]]]:
        """Get all the runs currently stored on the ot2

        Returns
        -------
        Optional[List[Dict[str, str]]]
            Returns a list of dictionaries that contain simplified information about the runs
        """
        runs_url = f"{self.base_url}/runs"
        runs_resp = requests.get(url=runs_url, headers=self.headers, timeout=10)

        if runs_resp.status_code == 200:
            runs_simplified = []
            for run in runs_resp.json()["data"]:
                runs_simplified.append(
                    {
                        "runID": run["id"],
                        "protocolID": run["protocolId"],
                        "status": run["status"],
                        "current": run["current"],
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
        runs = self.get_runs()
        if runs is None:
            return RobotStatus.OFFLINE.value

        for run in runs:
            run_status = run["status"]
            if run_status in {
                "succeeded",
                "stop-requested",
            }:  # Can't handle succeeded in client
                continue
            if run_status in [elem.value for elem in RunStatus]:
                return RobotStatus(run_status).value

        return RobotStatus.IDLE.value

    def reset_robot_data(self) -> None:
        """Reset the robot data remove failed runs and protocols"""
        delete_url = f"{self.base_url}/runs/"

        for run in self.get_runs():
            if run["status"] == "failed":
                requests.delete(
                    url=delete_url + run["runID"], headers=self.headers, timeout=10
                )

    def change_lights_status(self, status: bool = False) -> None:
        """switch the lights"""
        change_lights_url = f"{self.base_url}/robot/lights"
        payload = {"on": status}

        requests.post(change_lights_url, headers=self.headers, json=payload, timeout=10)

    def send_request(self, request_extension: str, **kwargs: Any) -> requests.Response:
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
        # sanitize preceding '/'
        request_extension = (
            request_extension if request_extension[0] != "/" else request_extension[1:]
        )
        url = f"{self.base_url}/{request_extension}"

        # check for headers
        if "headers" not in kwargs:
            kwargs["headers"] = {"Opentrons-Version": "2"}

        if "method" not in kwargs:
            raise Exception(
                "No request method specified, please provide GET, POST, UPDATE, DELETE as keyword argument"
            )
        kwargs["method"] = kwargs["method"].upper()

        return requests.request(url=url, **kwargs, timeout=10)

    def stream(
        self,
        command: str,
        params: dict,
        run_id: Optional[str] = None,
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

    def _stream(
        self,
        command: str,
        params: dict,
        run_id: Optional[str] = None,
        execute: bool = True,
        intent: Optional[str] = "setup",
    ) -> str:
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
                timeout=10,
            )
            run_id = run_resp.json()["data"]["id"]

        # queue the command
        enqueue_payload = {
            "data": {"commandType": command, "params": params, "intent": intent}
        }
        requests.post(
            url=f"{self.base_url}/runs/{run_id}/commands",
            headers=self.headers,
            json=enqueue_payload,
            max_retries=self.retry_strategy,
            timeout=10,
        )

        # run the command
        if execute:
            requests.post(
                url=f"{self.base_url}/runs/{run_id}/actions",
                headers=self.headers,
                json={"data": {"actionType": "play"}},
                max_retries=self.retry_strategy,
                timeout=10,
            )

        return run_id
