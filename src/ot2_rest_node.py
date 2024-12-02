#! /usr/bin/env python3
"""The server for the OT2 that takes incoming WEI flow requests from the experiment application"""
import ast
import glob
import json
import os
import traceback
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError

import requests
import yaml
from fastapi import UploadFile
from fastapi.datastructures import State
from typing_extensions import Annotated
from urllib3.exceptions import ConnectTimeoutError
from wei.modules.rest_module import RESTModule
from wei.types.module_types import AdminCommands, ModuleStatus
from wei.types.step_types import (
    ActionRequest,
    StepFileResponse,
    StepResponse,
    StepStatus,
)
from wei.utils import extract_version

from ot2_driver.ot2_driver_http import OT2_Config, OT2_Driver

workcell = None
global state
serial_port = "/dev/ttyUSB0"
local_ip = "parker.alcf.anl.gov"
local_port = "8000"

global ot2
resources_folder_path = ""
protocols_folder_path = ""
logs_folder_path = ""
node_name = ""
resource_file_path = ""
ip = ""


def check_protocols_folder(protocols_folder_path):
    """
    Description: Checks if the protocols folder path exists. Creates the resource folder path if it doesn't already exist
    """

    isPathExist = os.path.exists(protocols_folder_path)
    if not isPathExist:
        os.makedirs(protocols_folder_path)


def check_resources_folder(resources_folder_path):
    """
    Description: Checks if the resources folder path exists. Creates the resource folder path if it doesn't already exist
    """

    isPathExist = os.path.exists(resources_folder_path)
    if not isPathExist:
        os.makedirs(resources_folder_path)


def connect_robot(state: State):
    """Description: Connects to the ot2"""
    try:
        print(state.ip)
        state.ot2 = OT2_Driver(OT2_Config(ip=state.ip))
        state.status[ModuleStatus.READY] = True
        state.status[ModuleStatus.INIT] = False

    except ConnectTimeoutError as connection_err:
        state.status[ModuleStatus.READY] = False
        state.status[ModuleStatus.ERROR] = True
        print("Connection error code: " + connection_err)

    except HTTPError as http_error:
        print("HTTP error code: " + http_error)

    except URLError as url_err:
        print("Url error code: " + url_err)

    except requests.exceptions.ConnectionError as conn_err:
        print("Connection error code: " + str(conn_err))

    except Exception as error_msg:
        state.status[ModuleStatus.READY] = False
        state.status[ModuleStatus.ERROR] = True
        print("-------" + str(error_msg) + " -------")

    else:
        print(str(state.node_name) + " online")


def save_config_files(protocol: str, resource_config=None):
    """
    Saves protocol string to a local yaml or python file

    Parameters:
    -----------
    protocol: str
        String contents of yaml or python protocol file

    Returns
    -----------
    config_file_path: str
        Absolute path to generated yaml or python file
    """
    global node_name, resource_file_path
    config_dir_path = Path.home().resolve() / protocols_folder_path
    config_dir_path.mkdir(exist_ok=True, parents=True)

    resource_dir_path = Path.home().resolve() / resources_folder_path
    resource_dir_path.mkdir(exist_ok=True, parents=True)

    time_str = datetime.now().strftime("%Y%m%d-%H%m%s")

    config_file_path = None

    try:  # *Check if the protocol is a python file
        ast.parse(protocol)
        config_file_path = config_dir_path / f"protocol-{time_str}.py"
        with open(config_file_path, "w", encoding="utf-8") as pc_file:
            pc_file.write(protocol)
    except SyntaxError:
        try:  # *Check if the protocol is a yaml file
            config_file_path = config_dir_path / f"protocol-{time_str}.yaml"
            with open(config_file_path, "w", encoding="utf-8") as pc_file:
                yaml.dump(
                    yaml.safe_load(protocol),
                    pc_file,
                    indent=4,
                    sort_keys=False,
                    encoding="utf-8",
                )
        except yaml.YAMLError as e:
            raise ValueError("Protocol is neither a python file nor a yaml file") from e

    if resource_config:
        resource_file_path = resource_dir_path / f"resource-{node_name}-{time_str}.json"
        with open(resource_config) as resource_content:
            content = json.load(resource_content)
        json.dump(content, resource_file_path.open("w"))
        return config_file_path, resource_file_path
    else:
        return config_file_path, None


def execute(state, protocol_path, payload=None, resource_config=None):
    """
    Compiles the yaml at protocol_path into .py file;
    Transfers and Executes the .py file

    Parameters:
    -----------
    protocol_path: str
        absolute path to the yaml protocol

    Returns
    -----------
    response: bool
        If the ot2 execution was successful
    """

    if Path(protocol_path).suffix == ".yaml":
        print("YAML")
        (
            protocol_file_path,
            resource_file_path,
        ) = state.ot2.compile_protocol(
            protocol_path,
            payload=payload,
            resource_file=resource_config,
            resource_path=state.resources_folder_path,
            protocol_out_path=state.protocols_folder_path,
        )
        protocol_file_path = Path(protocol_file_path)
    else:
        print("PYTHON")
        protocol_file_path = Path(protocol_path)
    print(f"{protocol_file_path.resolve()=}")
    try:
        
        protocol_id, run_id = state.ot2.transfer(protocol_file_path)
        print("OT2 " + state.node_name + " protocol transfer successful")

        state.run_id = run_id
        resp = state.ot2.execute(run_id)
        state.run_id = None

        if resp["data"]["status"] == "succeeded":
            # poll_OT2_until_run_completion()
            print("OT2 " + state.node_name + " succeeded in executing a protocol")
            response_msg = (
                "OT2 " + state.node_name + " successfully IDLE running a protocol"
            )
            return "succeeded", response_msg, run_id

        elif resp["data"]["status"] == "stopped":
            print("OT2 " + state.node_name + " stopped while executing a protocol")
            response_msg = (
                "OT2 "
                + state.node_name
                + " successfully IDLE after stopping a protocol"
            )
            return "stopped", response_msg, run_id

        else:
            print("OT2 " + state.node_name + " failed in executing a protocol")
            print(resp["data"])
            response_msg = (
                "OT2 "
                + state.node_name
                + " failed running a protocol\n"
                + str(resp["data"])
            )
            return "failed", response_msg, run_id
    except Exception as err:
        if "no route to host" in str(err.args).lower():
            response_msg = "No route to host error. Ensure that this container \
            has network access to the robot and that the environment \
            variable, robot_ip, matches the ip of the connected robot \
            on the shared LAN."
            print(response_msg)

        response_msg = f"Error: {traceback.format_exc()}"
        print(response_msg)
        return False, response_msg, None


# def poll_OT2_until_run_completion():
#     """Queries the OT2 run state until reported as 'succeeded'"""
#     global run_id, state
#     print("Polling OT2 run until completion")
#     while state != ModuleStatus.IDLE:
#         run_status = ot2.get_run(run_id)

#         if run_status["data"]["status"] and run_status["data"]["status"] == "succeeded":
#             state = ModuleStatus.IDLE
#             print("Stopping Poll")

#         elif run_status["data"]["status"] and run_status["data"]["status"] == "running":
#             state = ModuleStatus.BUSY


rest_module = RESTModule(
    name="ot2_node",
    version=extract_version(Path(__file__).parent.parent / "pyproject.toml"),
    description="A node to control the OT2 liquid handling robot",
    model="ot2",
    admin_commands=set(
        [
            AdminCommands.LOCK,
            AdminCommands.UNLOCK,
            AdminCommands.RESUME,
            AdminCommands.PAUSE,
        ]
    ),
)

rest_module.arg_parser.add_argument("--ot2_ip", type=str, help="ot2 ip value")
rest_module.arg_parser.add_argument("--ot2_port", type=int, help="ot2 port value")


@rest_module.startup()
def ot2_startup(state: State):
    """Initial run function for the app, parses the workcell argument
    Parameters
    ----------
    app : FastApi
    The REST API app being initialized

    Returns
    -------
    None"""

    state.node_name = state.name
    state.ip = state.ot2_ip
    temp_dir = Path.home() / ".wei" / ".ot2_temp"
    temp_dir.mkdir(exist_ok=True)
    state.resources_folder_path = str(temp_dir / state.node_name / "resources/")
    state.protocols_folder_path = str(temp_dir / state.node_name / "protocols/")
    state.logs_folder_path = str(temp_dir / state.node_name / "logs/")
    state.run_id = None
    print(state.resources_folder_path)
    check_resources_folder(state.resources_folder_path)
    check_protocols_folder(state.protocols_folder_path)
    connect_robot(state)


@rest_module.action(name="run_protocol", description="Run a provided protocol file")
def run_protocol(
    state: State,
    action: ActionRequest,
    protocol: Annotated[UploadFile, "Protocol File"],
    use_existing_resources: Annotated[
        bool, "Whether to use the existing resource file or restart"
    ] = False,
):
    """
    Run a given protocol
    """

    resource_config = None

    if use_existing_resources:
        try:
            list_of_files = glob.glob(
                state.resources_folder_path + "*.json"
            )  # Get list of files
            if len(list_of_files) > 0:
                resource_config = max(
                    list_of_files, key=os.path.getctime
                )  # Finding the latest added file
                print("Using the resource file: " + resource_config)

        except Exception as er:
            print(er)

    # * Get the protocol file
    try:
        protocol = next(file for file in action.files if file.filename == "protocol")
        protocol = protocol.file.read().decode("utf-8")
    except StopIteration:
        protocol = None

    print(f"{protocol=}")

    if protocol:
        config_file_path, resource_config_path = save_config_files(
            protocol, resource_config
        )
        payload = deepcopy(action.args)

        print(f"ot2 {payload=}")
        print(f"config_file_path: {config_file_path}")

        response_flag, response_msg, run_id = execute(
            state, config_file_path, payload, resource_config_path
        )

        response = None

        if response_flag == "succeeded":
            state.status[ModuleStatus.READY] = True
            Path(logs_folder_path).mkdir(parents=True, exist_ok=True)
            with open(Path(logs_folder_path) / f"{run_id}.json", "w") as f:
                json.dump(state.ot2.get_run_log(run_id), f, indent=2)
                return StepFileResponse(
                    status=StepStatus.SUCCEEDED, files={"log": f.name}
                )
            # if resource_config_path:
            #   response.resources = str(resource_config_path)
        elif response_flag == "stopped":
            state.status[ModuleStatus.READY] = True
            Path(logs_folder_path).mkdir(parents=True, exist_ok=True)
            with open(Path(logs_folder_path) / f"{run_id}.json", "w") as f:
                json.dump(state.ot2.get_run_log(run_id), f, indent=2)
                return StepFileResponse(status=StepStatus.FAILED, files={"log": f.name})

        elif response_flag == "failed":
            state.status[ModuleStatus.READY] = False
            state.status[ModuleStatus.ERROR] = True
            response = StepResponse
            response.status = StepStatus.FAILED
            response.error = "an error occurred"
            # if resource_config_path:
            #   response.resources = str(resource_config_path)

        return response

    else:
        response["action_msg"] = "Required 'protocol' file was not provided"
        response.action_response = StepStatus.FAILED
        print(response.action_msg)
        state = ModuleStatus.ERROR

        return response


@rest_module.pause()
def pause(state: State):
    """pauses the ot2 run"""
    if state.run_id is not None:
        state.ot2.pause(state.run_id)
        state.status[ModuleStatus.PAUSED] = True


@rest_module.resume()
def resume(state: State):
    """resumes paused ot2_run"""
    if state.run_id is not None and state.status[ModuleStatus.PAUSED]:
        state.ot2.resume(state.run_id)
        state.status[ModuleStatus.PAUSED] = False


@rest_module.cancel()
def cancel(state: State):
    """cancels ot2 run"""
    if state.run_id is not None:
        state.ot2.cancel(state.run_id)
        state.status[ModuleStatus.PAUSED] = False
        state.status[ModuleStatus.CANCELLED] = True


rest_module.start()
