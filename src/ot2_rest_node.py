#! /usr/bin/env python3
"""OT2 Node Module implementation"""

import traceback
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import requests
from madsci.client.resource_client import ResourceClient
from madsci.common.types.action_types import ActionFailed, ActionSucceeded
from madsci.common.types.auth_types import OwnershipInfo
from madsci.common.types.node_types import RestNodeConfig
from madsci.common.types.resource_types.definitions import (
    ContainerResourceDefinition,
    SlotResourceDefinition,
)
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode
from ot2_interface.ot2_driver_http import OT2_Config, OT2_Driver
from typing_extensions import Annotated
from urllib3.exceptions import ConnectTimeoutError


class OT2NodeConfig(RestNodeConfig):
    """Configuration for the OT2 node module."""

    __test__ = False

    ot2_ip: str
    "ip of opentrons device"


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
        self.protocols_folder_path = str(
            temp_dir / self.node_definition.node_name / "protocols/"
        )
        if self.config.resource_server_url:
            self.resource_client = ResourceClient(self.config.resource_server_url)
            self.resource_owner = OwnershipInfo(node_id=self.node_definition.node_id)
            self.deck = self.resource_client.init_resource(
                ContainerResourceDefinition(
                    resource_name="ot2_" + self.node_definition.node_name + "_deck",
                    owner=self.resource_owner,
                )
            )

            for i in range(1, 13):
                rec_def = SlotResourceDefinition(
                    resource_name="ot2_"
                    + self.node_definition.node_name
                    + "_deck"
                    + str(i),
                    owner=self.resource_owner,
                )
                try:
                    self.resource_client.set_child(
                        self.deck, str(i), self.resource_client.init_resource(rec_def)
                    )
                except Exception:
                    print("Already has child")
            self.pipette_slots = {}
            self.pipette_slots["left"] = self.resource_client.init_resource(
                SlotResourceDefinition(
                    resource_name="ot2_"
                    + self.node_definition.node_name
                    + "_left_pipette_slot",
                    owner=self.resource_owner,
                )
            )
            self.pipette_slots["right"] = self.resource_client.init_resource(
                SlotResourceDefinition(
                    resource_name="ot2_"
                    + self.node_definition.node_name
                    + "_right_pipette_slot",
                    owner=self.resource_owner,
                )
            )

        else:
            self.resource_client = None
            self.deck_slots = None
        # TODO: eventual path for resources?
        # TODO: setup logs folder path?
        self.run_id = None
        self.ip = self.config.ot2_ip
        # TODO: check if resource and protocols folders exist, if not create them
        self.ot2_interface = None
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
                #  "test_status_code": self.ot2_interface.status_code,
            }

    def connect_robot(self) -> None:
        """Description: Connects to the ot2"""
        try:
            self.ot2_interface = OT2_Driver(OT2_Config(ip=self.config.ot2_ip))

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
        protocol: Annotated[Path, "Protocol File"],
        parameters: Annotated[
            dict[str, Any], "Parameters for insertion into the protocol"
        ] = {},
        # TODO: whether or not to use existing resources?
    ) -> Annotated[dict[str, Any], "ot2 action log"]:
        """
        Run a given protocol on the ot2
        """
        # TODO: if use existing resources.... (find and use a ot2 json file)

        # get the next protocol file

        if protocol:
            with protocol.open(mode="r") as f:
                file_text = f.read()
                for key in parameters.keys():
                    file_text = file_text.replace("$" + key, str(parameters[key]))
            with protocol.open(mode="w") as f:
                f.write(file_text)
            response_flag, response_msg, run_id = self.execute(protocol, parameters)
            if self.resource_client is not None:
                self.parse_logs(self.ot2_interface.get_run_log(run_id))

            if response_flag == "succeeded":
                # TODO logging
                pass
                # Path(logs_folder_path).mkdir(parents=True, exist_ok=True)
                # with open(Path(logs_folder_path) / f"{run_id}.json", "w") as f:
                #     json.dump(state.ot2.get_run_log(run_id), f, indent=2)
                #     return StepFileResponse(
                #         status=StepStatus.SUCCEEDED, files={"log": f.name}
                #     )
                # if resource_config_path:
                #   response.resources = str(resource_config_path)
                return self.ot2_interface.get_run_log(run_id)
            elif response_flag == "stopped":
                pass
                # Path(logs_folder_path).mkdir(parents=True, exist_ok=True)
                # with open(Path(logs_folder_path) / f"{run_id}.json", "w") as f:
                #     json.dump(state.ot2.get_run_log(run_id), f, indent=2)
                #     return StepFileResponse(status=StepStatus.FAILED, files={"log": f.name})
                raise Exception("Run was stopped")
            elif response_flag == "failed":
                pass
                # response = StepResponse()
                # response.status = StepStatus.FAILED
                # response.error = "an error occurred"
                # if resource_config_path:
                #   response.resources = str(resource_config_path)
                raise Exception("Run failed: " + response_msg)
        else:
            raise Exception("No protocol file found")

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
            protocol_id, run_id = self.ot2_interface.transfer(protocol_file_path)
            self.logger.log(
                "OT2 "
                + self.node_definition.node_name
                + " protocol transfer successful"
            )

            self.run_id = run_id
            resp = self.ot2_interface.execute(run_id)
            self.run_id = None
            print(resp)
            if resp["data"]["status"] == "succeeded":
                # poll_OT2_until_run_completion()
                self.logger.log(
                    "OT2 "
                    + self.node_definition.node_name
                    + " succeeded in executing a protocol"
                )
                response_msg = (
                    "OT2 "
                    + self.node_definition.node_name
                    + " successfully IDLE running a protocol"
                )
                return "succeeded", response_msg, run_id

            elif resp["data"]["status"] == "stopped":
                self.logger.log(
                    "OT2 "
                    + self.node_definition.node_name
                    + " stopped while executing a protocol"
                )
                response_msg = (
                    "OT2 "
                    + self.node_definition.node_name
                    + " successfully IDLE after stopping a protocol"
                )
                return "stopped", response_msg, run_id

            else:
                self.logger.log(
                    "OT2 "
                    + self.node_definition.node_name
                    + " failed in executing a protocol"
                )
                self.logger.log(resp["data"])
                response_msg = (
                    "OT2 "
                    + self.node_definition.node_name
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

    def pause(self) -> None:
        """Pause the node."""
        self.logger.log("Pausing node...")
        self.ot2_interface.pause(self.run_id)
        self.node_status.paused = True
        self.logger.log("Node paused.")
        return True

    def resume(self) -> None:
        """Resume the node."""
        self.logger.log("Resuming node...")
        self.ot2_interface.resume(self.run_id)
        self.node_status.paused = False
        self.logger.log("Node resumed.")
        return True

    # TODO: shutdown, safety stop, reset
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
        self.ot2_interface.cancel(self.run_id)
        self.node_status.cancelled = True
        self.logger.log("Node cancelled.")
        return True

    def find_resource(self, logs: Any, command: Any):
        """Extract resource information from logs"""
        labwares = logs["data"]["labware"]
        labware_id = command["params"]["labwareId"]
        labware = next(labware for labware in labwares if labware["id"] == labware_id)
        resource = self.deck_slots[labware["location"]["slotName"]]
        return resource

    def parse_logs(self, logs: Any):
        """Extract useful information from the ot2's logs"""
        try:
            for command in logs["commands"]["data"]:
                if command["commandType"] == "aspirate":
                    resource = self.find_resource(logs, command)
                    print(resource)
                    # self.resource_client.decrease_resource(command["params"]["volume"])
                elif command["commandType"] == "dispense":
                    resource = self.find_resource(logs, command)
                    print(resource)
                    # self.resource_client.decrease_resource(command["params"]["volume"])
                elif command["commandType"] == "pickUpTip":
                    resource = self.find_resource(logs, command)

                    print(resource)
                elif command["commandType"] == "dropTip":
                    resource = self.find_resource(logs, command)

                    print(resource)
                    # self.resource_client.decrease_resource(command["params"]["volume"])
        except Exception:
            print("Couldn't update resources, no longer tracked")


if __name__ == "__main__":
    ot2_node = OT2Node()
    ot2_node.start_node()
