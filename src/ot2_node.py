from typing import Optional
from pathlib import Path
from urllib.error import HTTPError, URLError
import requests
from typing_extensions import Annotated
from fastapi import UploadFile
import ast
from datetime import datetime
from copy import deepcopy
from urllib3.exceptions import ConnectTimeoutError
import traceback


from madsci.client.event_client import EventClient
from madsci.common.types.action_types import ActionFailed, ActionSucceeded
from madsci.common.types.node_types import RestNodeConfig
from madsci.node_module.abstract_node_module import action
from madsci.node_module.rest_node_module import RestNode

from ot2_driver.ot2_driver_http import OT2_Config, OT2_Driver

class OT2NodeConfig(RestNodeConfig):
    """Configuration for the OT2 node module."""

    __test__ = False

    # test_required_param: int
    # """A required parameter."""
    # test_optional_param: Optional[int] = None
    # """An optional parameter."""
    # test_default_param: int = 42
    # """A parameter with a default value."""
    serial_port: str = "/dev/ttyUSB0"
    """Serial port connection for OT2"""
    local_ip: str = "parker.alcf.anl.gov"
    """local ip for computer running ot2 node"""
    local_port: str = "8000"
    """local port for ot2 node"""
    name: str
    """name of node being used is required"""
    ip: str = "" #TODO: is currently command line
    "ip of opentrons device"
    port: int = 0000 #TODO: is currently command line
    "port of opentrons device"


class OT2Node(RestNode):
    """Node module for Opentrons Robots"""

    __test__ = False
    ot2_interface: OT2_Driver
    config_model = OT2NodeConfig

    def startup_handler(self) -> None:
        """Called to (re)initialize the node. Should be used to open connections to devices or initialize any other resources."""
        self.logger.log("Node initializing...")
        temp_dir = Path.home() / ".madsci" / ".ot2_temp"
        temp_dir.mkdir(exist_ok=True)
        self.protocols_folder_path = str(temp_dir / self.config_model.name / "protocols/")
        #TODO: eventual path for resources?
        #TODO: setup logs folder path?
        self.run_id = None
        self.ip = self.config_model.ip
        #TODO: check if resource and protocols folders exist, if not create them
        self.connect_robot()
        self.startup_has_run = True
        self.logger.log("OT2 node initialized!")

    def shutdown_handler(self) -> None:
        """Called to shutdown the node. Should be used to close connections to devices or release any other resources."""
        self.logger.log("Shutting down")
        self.shutdown_has_run = True
        del self.ot2_interface
        self.ot2_interface = None
        self.logger.log("Shutdown complete.")

    def state_handler(self) -> None:
        """Periodically called to update the current state of the node."""
        if self.ot2_interface is not None:
            self.node_state = {
                "test_status_code": self.ot2_interface.status_code,
            }


    def connect_robot(self) -> None:
        """Description: Connects to the ot2"""
        try:
            self.ot2 = OT2_Driver(OT2_Config(ip=self.config_model.ip))

        except ConnectTimeoutError as connection_err:
            self.node_status.errored = True
            print("Connection error code: " + connection_err)

        except HTTPError as http_error:
            print("HTTP error code: " + http_error)

        except URLError as url_err:
            print("Url error code: " + url_err)

        except requests.exceptions.ConnectionError as conn_err:
            print("Connection error code: " + str(conn_err))

        except Exception as error_msg:
            self.node_status.errored = True
            print("-------" + str(error_msg) + " -------")

        else:
            self.logger.log("OT2 node online")


    @action(name="run_protocol", description="run a given opentrons protocol")
    def run_protocol(
        self,
        protocol: Annotated[UploadFile, "Protocol File"]
        #TODO: whether or not to use existing resources?
    ):
        """
        Run a given protocol on the ot2
        """
        #TODO: if use existing resources.... (find and use a ot2 json file)

        #get the next protocol file
        try:
            protocol = next(file for file in action.files if file.filename == "protocol")
            protocol = protocol.file.read().decode("utf-8")
        except StopIteration:
            protocol = None
        
        if protocol:
            config_file_path = self.save_config_files(
                protocol
            )
            payload = deepcopy(action.args)

            response_flag, response_msg, run_id = self.execute(
                config_file_path, payload
            )

            response = None

            if response_flag == "succeeded":
                #TODO logging
                pass
                # Path(logs_folder_path).mkdir(parents=True, exist_ok=True)
                # with open(Path(logs_folder_path) / f"{run_id}.json", "w") as f:
                #     json.dump(state.ot2.get_run_log(run_id), f, indent=2)
                #     return StepFileResponse(
                #         status=StepStatus.SUCCEEDED, files={"log": f.name}
                #     )
                # if resource_config_path:
                #   response.resources = str(resource_config_path)
            elif response_flag == "stopped":
                pass
                # Path(logs_folder_path).mkdir(parents=True, exist_ok=True)
                # with open(Path(logs_folder_path) / f"{run_id}.json", "w") as f:
                #     json.dump(state.ot2.get_run_log(run_id), f, indent=2)
                #     return StepFileResponse(status=StepStatus.FAILED, files={"log": f.name})

            elif response_flag == "failed":
                pass
                # response = StepResponse()
                # response.status = StepStatus.FAILED
                # response.error = "an error occurred"
                # if resource_config_path:
                #   response.resources = str(resource_config_path)

            return response
        else:
            response["action_msg"] = "Required 'protocol' file was not provided"
            print(response.action_msg)

            return response


    def execute(self, protocol_path, payload=None, resource_config=None):
        """
        Transfers and Executes the .py protocol file

        Parameters:
        -----------
        protocol_path: str
            absolute path to the yaml protocol

        Returns
        -----------
        response: bool
            If the ot2 execution was successful
        """

        protocol_file_path = Path(protocol_path)
        self.logger.log(f"{protocol_file_path.resolve()=}")
        try:
            protocol_id, run_id = self.ot2.transfer(protocol_file_path)
            self.logger.log("OT2 " + self.config_model.name + " protocol transfer successful")

            self.run_id = run_id
            resp = self.ot2.execute(run_id)
            self.run_id = None

            if resp["data"]["status"] == "succeeded":
                # poll_OT2_until_run_completion()
                self.logger.log("OT2 " + self.config_model.name + " succeeded in executing a protocol")
                response_msg = (
                    "OT2 " + self.config_model.name + " successfully IDLE running a protocol"
                )
                return "succeeded", response_msg, run_id

            elif resp["data"]["status"] == "stopped":
                self.logger.log("OT2 " + self.config_model.name + " stopped while executing a protocol")
                response_msg = (
                    "OT2 "
                    + self.config_model.name
                    + " successfully IDLE after stopping a protocol"
                )
                return "stopped", response_msg, run_id

            else:
                self.logger.log("OT2 " + self.config_model.name + " failed in executing a protocol")
                self.logger.log(resp["data"])
                response_msg = (
                    "OT2 "
                    + self.config_model.name
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
                self.logger.log(response_msg)

            response_msg = f"Error: {traceback.format_exc()}"
            print(response_msg)
            return False, response_msg, None


    def save_config_files(self, protocol: str, resource_config=None):
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
        config_dir_path = Path.home().resolve() / self.protocols_folder_path
        config_dir_path.mkdir(exist_ok=True, parents=True)

        #TODO: resources
        # resource_dir_path = Path.home().resolve() / resources_folder_path
        # resource_dir_path.mkdir(exist_ok=True, parents=True)

        time_str = datetime.now().strftime("%Y%m%d-%H%m%s")

        config_file_path = None

        try:  # *Check if the protocol is a python file
            ast.parse(protocol)
            config_file_path = config_dir_path / f"protocol-{time_str}.py"
            with open(config_file_path, "w", encoding="utf-8") as pc_file:
                pc_file.write(protocol)
        except SyntaxError:
            self.logger.log("Error: no protocol python file detected")
        
        #TODO: json dump of resources

        return config_file_path

    def pause(self) -> None:
        """Pause the node."""
        self.logger.log("Pausing node...")
        self.node_status.paused = True
        self.logger.log("Node paused.")
        return True

    def resume(self) -> None:
        """Resume the node."""
        self.logger.log("Resuming node...")
        self.node_status.paused = False
        self.logger.log("Node resumed.")
        return True

    def shutdown(self) -> None:
        """Shutdown the node."""
        self.shutdown_handler()
        return True

    def reset(self) -> None:
        """Reset the node."""
        self.logger.log("Resetting node...")
        result = super().reset()
        self.logger.log("Node reset.")
        return result

    def safety_stop(self) -> None:
        """Stop the node."""
        self.logger.log("Stopping node...")
        self.node_status.stopped = True
        self.logger.log("Node stopped.")
        return True

    def cancel(self) -> None:
        """Cancel the node."""
        self.logger.log("Canceling node...")
        self.node_status.cancelled = True
        self.logger.log("Node cancelled.")
        return True
    
if __name__ == "__main__":
    ot2_node = OT2Node()
    ot2_node.start_node()