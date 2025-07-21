#! /usr/bin/env python3
"""OT2 Node Module implementation"""

import ast
import contextlib
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Optional, Union

from madsci.common.types.action_types import (
    ActionCancelled,
    ActionFailed,
    ActionSucceeded,
)
from madsci.common.types.node_types import RestNodeConfig
from madsci.common.types.resource_types.definitions import (
    ContainerResourceDefinition,
    SlotResourceDefinition,
)
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode

from ot2_interface.ot2_driver_http import OpentronsInterface


class OT2NodeConfig(RestNodeConfig):
    """Configuration for the OT2 node module."""

    ot2_ip: Optional[str] = None
    "IP address of the Opentrons device"
    ot2_port: int = 31950
    "Port of the Opentrons device, default is 31950"


class OT2Node(RestNode):
    """Node module for Opentrons Robots"""

    ot2_interface: OpentronsInterface
    config: OT2NodeConfig = OT2NodeConfig()
    config_model = OT2NodeConfig

    run_id = None
    """ID of the currently running protocol"""
    protocols_folder_path = Path(tempfile.mkdtemp(prefix="ot2_protocols_"))
    """Path to the folder where protocols are saved"""

    def startup_handler(self) -> None:
        """Called to (re)initialize the node. Should be used to open connections to devices or initialize any other resources."""
        if self.config.ot2_ip is None:
            raise ValueError(
                "OT2 IP address must be set in the configuration before starting the node."
            )
        self.ot2_interface = OpentronsInterface(
            ot2_ip=self.config.ot2_ip,
            ot2_port=self.config.ot2_port,
        )

        if self.resource_client:
            self.deck = self.resource_client.init_resource(
                ContainerResourceDefinition(
                    resource_name=self.node_definition.node_name + "_deck",
                )
            )

            for i in range(1, 13):
                rec_def = SlotResourceDefinition(
                    resource_name=self.node_definition.node_name + "_deck" + str(i),
                )
                with contextlib.suppress(Exception):
                    self.resource_client.set_child(
                        self.deck, str(i), self.resource_client.init_resource(rec_def)
                    )
            self.pipette_slots = {}
            self.pipette_slots["left"] = self.resource_client.init_resource(
                SlotResourceDefinition(
                    resource_name=self.node_definition.node_name + "_left_pipette_slot",
                )
            )
            self.pipette_slots["right"] = self.resource_client.init_resource(
                SlotResourceDefinition(
                    resource_name=self.node_definition.node_name
                    + "_right_pipette_slot",
                )
            )

        else:
            self.deck_slots = None

    def shutdown_handler(self) -> None:
        """Called to shutdown the node. Should be used to close connections to devices or release any other resources."""
        del self.ot2_interface
        self.ot2_interface = None

    @action(name="run_protocol", description="run a given opentrons protocol")
    def run_protocol(
        self,
        protocol: Annotated[Path, "Protocol File"],
        parameters: Annotated[
            dict[str, Any], "Parameters for insertion into the protocol"
        ] = {},
    ) -> Union[ActionSucceeded, ActionCancelled, ActionFailed]:
        """
        Run a provided Opentrons protocol file on the connected Opentrons robot.
        """

        with protocol.open(mode="r") as f:
            file_text = f.read()
            for key in parameters:
                file_text = file_text.replace("$" + key, str(parameters[key]))
        with protocol.open(mode="w") as f:
            f.write(file_text)
        config_file_path = self.save_config_files(protocol)
        response_flag, _, run_id = self.execute(config_file_path)
        if False:  # TODO: Resource handling
            self.parse_logs(self.ot2_interface.get_run_log(run_id))

        response = ActionFailed()
        if response_flag == "succeeded":
            response = ActionSucceeded(
                data={"log_value": self.ot2_interface.get_run_log(run_id)}
            )
        elif response_flag == "stopped":
            response = ActionCancelled(
                errors=f"OT2 stopped during protocol run: {run_id}",
                data={"log_value": self.ot2_interface.get_run_log(run_id)},
            )
        elif response_flag == "failed":
            response = ActionFailed(
                errors=f"OT2 failed during protocol run: {run_id}",
                data={"log_value": self.ot2_interface.get_run_log(run_id)},
            )
        else:
            response = ActionFailed(errors=f"Unknown response: {response_flag}. ")
        return response

    def execute(
        self, protocol_path: Union[Path, str]
    ) -> tuple[str, str, Optional[str]]:
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

        protocol_id, run_id = self.ot2_interface.transfer(protocol_file_path)
        self.logger.log(
            "OT2 " + self.node_definition.node_name + " protocol transfer successful"
        )

        self.run_id = run_id
        resp = self.ot2_interface.execute(run_id)
        self.run_id = None
        if resp["data"]["status"] == "succeeded":
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

        if resp["data"]["status"] == "stopped":
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

        self.logger.log(
            "OT2 " + self.node_definition.node_name + " failed in executing a protocol"
        )
        self.logger.log(resp["data"])
        response_msg = (
            "OT2 "
            + self.node_definition.node_name
            + " failed running a protocol\n"
            + str(resp["data"])
        )
        return "failed", response_msg, run_id

    def save_config_files(self, protocol: Path) -> Optional[Path]:
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
        config_dir_path = self.protocols_folder_path
        config_dir_path.mkdir(exist_ok=True, parents=True)

        time_str = datetime.now().strftime("%Y%m%d-%H%m%s")

        config_file_path = None
        try:  # *Check if the protocol is a python file
            ast.parse(protocol.open(mode="r").read())

            config_file_path = config_dir_path / f"protocol-{time_str}.py"
            text = protocol.open(mode="r").read()
            with config_file_path.open("w", encoding="utf-8") as pc_file:
                pc_file.write(text)
        except SyntaxError:
            self.logger.log("Error: no protocol python file detected")

        return config_file_path

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

    def find_resource(self, logs: Any, command: Any) -> SlotResourceDefinition:
        """Extract resource information from logs"""
        labwares = logs["data"]["labware"]
        labware_id = command["params"]["labwareId"]
        labware = next(labware for labware in labwares if labware["id"] == labware_id)
        return self.deck_slots[labware["location"]["slotName"]]

    def parse_logs(self, logs: Any) -> None:
        """Extract useful information from the ot2's logs"""
        try:
            for command in logs["commands"]["data"]:
                if (
                    command["commandType"] == "aspirate"
                    or command["commandType"] == "dispense"
                    or command["commandType"] == "pickUpTip"
                    or command["commandType"] == "dropTip"
                ):
                    _ = self.find_resource(logs, command)
                    # self.resource_client.decrease_resource(command["params"]["volume"])  # noqa: ERA001
        except Exception:
            self.logger.error("Error while parsing logs: " + traceback.format_exc())


if __name__ == "__main__":
    ot2_node = OT2Node()
    ot2_node.start_node()
