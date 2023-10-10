#! /usr/bin/env python3
"""The server for the OT2 that takes incoming WEI flow requests from the experiment application"""
import glob
import json
import os
import time
import traceback
from argparse import ArgumentParser
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError

import requests
import yaml
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from urllib3.exceptions import ConnectTimeoutError

from ot2_driver.ot2_driver_http import OT2_Config, OT2_Driver

workcell = None
global state
serial_port = "/dev/ttyUSB0"
local_ip = "parker.alcf.anl.gov"
local_port = "8000"

global ot2
resources_folder_path = ""
protocols_folder_path = ""
node_name = ""
resource_file_path = ""
ip = ""


def check_protocols_folder():
    """
    Description: Checks if the protocols folder path exists. Creates the resource folder path if it doesn't already exist
    """
    global protocols_folder_path
    isPathExist = os.path.exists(protocols_folder_path)
    if not isPathExist:
        os.makedirs(protocols_folder_path)


def check_resources_folder():
    """
    Description: Checks if the resources folder path exists. Creates the resource folder path if it doesn't already exist
    """
    global resources_folder_path
    isPathExist = os.path.exists(resources_folder_path)
    if not isPathExist:
        os.makedirs(resources_folder_path)
    if not isPathExist:
        os.makedirs(protocols_folder_path)
        print("Creating: " + protocols_folder_path)


def connect_robot():
    global ot2, state, node_name, ip
    try:
        print(ip)
        ot2 = OT2_Driver(OT2_Config(ip=ip))

    except ConnectTimeoutError as connection_err:
        state = "ERROR"
        print("Connection error code: " + connection_err)

    except HTTPError as http_error:
        print("HTTP error code: " + http_error)

    except URLError as url_err:
        print("Url error code: " + url_err)

    except requests.exceptions.ConnectionError as conn_err:
        print("Connection error code: " + str(conn_err))

    except Exception as error_msg:
        state = "ERROR"
        print("-------" + str(error_msg) + " -------")

    else:
        print(str(node_name) + " online")


def download_config_files(protocol_config: str, resource_config=None):
    """
    Saves protocol_config string to a local yaml file location

    Parameters:
    -----------
    protocol_config: str
        String contents of yaml protocol file

    Returns
    -----------
    config_file_path: str
        Absolute path to generated yaml file
    """
    global node_name, resource_file_path
    config_dir_path = Path.home().resolve() / protocols_folder_path
    config_dir_path.mkdir(exist_ok=True, parents=True)

    resource_dir_path = Path.home().resolve() / resources_folder_path
    resource_dir_path.mkdir(exist_ok=True, parents=True)

    time_str = datetime.now().strftime("%Y%m%d-%H%m%s")
    config_file_path = config_dir_path / f"protocol-{time_str}.yaml"

    print("Writing protocol config to {} ...".format(str(config_file_path)))

    with open(config_file_path, "w", encoding="utf-8") as pc_file:
        yaml.dump(protocol_config, pc_file, indent=4, sort_keys=False)
    if resource_config:
        resource_file_path = resource_dir_path / f"resource-{node_name}-{time_str}.json"
        with open(resource_config) as resource_content:
            content = json.load(resource_content)
        json.dump(content, resource_file_path.open("w"))
        return config_file_path, resource_file_path
    else:
        return config_file_path, None


def execute(protocol_path, payload=None, resource_config=None):
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

    global run_id, node_name, protocols_folder_path, resources_folder_path
    try:
        (
            protocol_file_path,
            resource_file_path,
        ) = ot2.compile_protocol(
            protocol_path,
            payload=payload,
            resource_file=resource_config,
            resource_path=resources_folder_path,
            protocol_out_path=protocols_folder_path,
        )
        protocol_file_path = Path(protocol_file_path)
        print(f"{protocol_file_path.resolve()=}")
        protocol_id, run_id = ot2.transfer(protocol_file_path)
        print("OT2 " + node_name + " protocol transfer successful")
        resp = ot2.execute(run_id)
        print("OT2 " + node_name + " executed a protocol")

        if resp["data"]["status"] == "succeeded":
            # poll_OT2_until_run_completion()
            response_msg = "OT2 " + node_name + " successfully IDLE running a protocol"
            return True, response_msg

        else:
            response_msg = "OT2 " + node_name + " failed running a protocol"
            return False, response_msg
    except Exception as err:
        if "no route to host" in str(err.args).lower():
            response_msg = "No route to host error. Ensure that this container \
            has network access to the robot and that the environment \
            variable, robot_ip, matches the ip of the connected robot \
            on the shared LAN."
            print(response_msg)

        response_msg = f"Error: {traceback.format_exc()}"
        print(response_msg)
        return False, response_msg


def poll_OT2_until_run_completion():
    """Queries the OT2 run state until reported as 'succeeded'"""
    global run_id, state
    print("Polling OT2 run until completion")
    while state != "IDLE":
        run_status = ot2.get_run(run_id)

        if run_status["data"]["status"] and run_status["data"]["status"] == "succeeded":
            state = "IDLE"
            print("Stopping Poll")

        elif run_status["data"]["status"] and run_status["data"]["status"] == "running":
            state = "BUSY"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ot2, state, node_name, resources_folder_path, protocols_folder_path, ip
    """Initial run function for the app, parses the workcell argument
            Parameters
            ----------
            app : FastApi
            The REST API app being initialized

            Returns
            -------
            None"""
    parser = ArgumentParser()
    parser.add_argument("--alias", type=str, help="Name of the Node")
    parser.add_argument("--host", type=str, help="Host for rest")
    parser.add_argument("--ot2_ip", type=str, help="ip value")
    parser.add_argument("--port", type=int, help="port value")
    args = parser.parse_args()
    node_name = args.alias
    ip = args.ot2_ip
    state = "UNKNOWN"
    resources_folder_path = "/home/rpl/.ot2_temp/" + node_name + "/" + "resources/"
    protocols_folder_path = "/home/rpl/.ot2_temp/" + node_name + "/" + "protocols/"
    check_resources_folder()
    check_protocols_folder()
    connect_robot()
    state = "IDLE"
    yield
    pass


app = FastAPI(
    lifespan=lifespan,
)


@app.get("/state")
def get_state():
    global state
    return JSONResponse(content={"State": state})


@app.get("/description")
async def description():
    global state
    return JSONResponse(content={"State": state})


@app.get("/resources")
async def resources():
    global resource_file_path
    resource_info = ""
    if not (resource_file_path == ""):
        with open(resource_file_path) as f:
            resource_info = f.read()
    return JSONResponse(content={"State": resource_info})


@app.post("/action")
def do_action(action_handle: str, action_vars):
    global ot2, state
    response = {"action_response": "", "action_msg": "", "action_log": ""}
    if state == "ERROR":
        msg = "Can not accept the job! OT2 CONNECTION ERROR"
        # get_logger.error(msg)
        response["action_response"] = -1
        response["action_msg"] = msg
        return response

    while state != "IDLE":
        #   get_logger().warn("Waiting for OT2 to switch IDLE state...")
        time.sleep(0.5)

    state = "BUSY"
    action_command = action_handle
    action_vars = json.loads(action_vars)
    print(f"{action_vars=}")

    print(f"In action callback, command: {action_command}")

    if "run_protocol" == action_command:
        protocol_config = action_vars.get("config_path", None)
        resource_config = action_vars.get(
            "resource_path", None
        )  # TODO: This will be enabled in the future
        resource_file_flag = action_vars.get(
            "use_existing_resources", "False"
        )  # Returns True to use a resource file or False to not use a resource file.

        if resource_file_flag:
            try:
                list_of_files = glob.glob(
                    resources_folder_path + "*.json"
                )  # Get list of files
                if len(list_of_files) > 0:
                    resource_config = max(
                        list_of_files, key=os.path.getctime
                    )  # Finding the latest added file
                    print("Using the resource file: " + resource_config)

            except Exception as er:
                print(er)
        if protocol_config:
            config_file_path, resource_config_path = download_config_files(
                protocol_config, resource_config
            )
            payload = deepcopy(action_vars)
            payload.pop("config_path")

            print(f"ot2 {payload=}")
            print(f"config_file_path: {config_file_path}")

            response_flag, response_msg = execute(
                config_file_path, payload, resource_config_path
            )

            if response_flag:
                state = "IDLE"
                response["action_response"] = 0
                response["action_msg"] = response_msg
                # if resource_config_path:
                #   response.resources = str(resource_config_path)

            elif not response_flag:
                state = "ERROR"
                response["action_response"] = -1
                response["action_msg"] = response_msg
                # if resource_config_path:
                #   response.resources = str(resource_config_path)

            print("Finished Action: " + action_handle)
            return response

        else:
            response[
                "action_msg"
            ] = "Required 'config' was not specified in action_vars"
            response["action_response"] = -1
            print(response["action_msg"])
            state = "ERROR"

            return response
    else:
        msg = "UNKNOWN ACTION REQUEST! Available actions: run_protocol"
        response["action_response"] = -1
        response["action_msg"] = msg
        print("Error: " + msg)
        state = "IDLE"

        return response


if __name__ == "__main__":
    import uvicorn

    parser = ArgumentParser()
    parser.add_argument("--alias", type=str, help="Name of the Node")
    parser.add_argument("--host", type=str, help="Host for rest")
    parser.add_argument("--ot2_ip", type=str, help="ip value")
    parser.add_argument("--port", type=int, help="port value")
    args = parser.parse_args()
    node_name = args.alias
    ip = args.ot2_ip
    uvicorn.run(
        "ot2_rest_client:app",
        host=args.host,
        port=args.port,
        reload=False,
        ws_max_size=100000000000000000000000000000000000000,
    )
