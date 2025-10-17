#! /usr/bin/env python3
"""OT2 Node Module implementation"""

import traceback
from pathlib import Path
from typing import Any, Optional

from madsci.common.types.node_types import RestNodeConfig
from madsci.common.types.resource_types import Container, Pool, Slot, Stack
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode
from ot2_interface.ot2_driver_http import OT2_Config, OT2_Driver
from typing_extensions import Annotated


class OT2NodeConfig(RestNodeConfig):
    """Configuration for the OT2 node module."""

    ot2_ip: Optional[str] = None
    "ip of opentrons device"


class OT2Node(RestNode):
    """Node module for Opentrons Robots"""

    ot2_interface: OT2_Driver = None
    config: OT2NodeConfig = OT2NodeConfig()
    config_model = OT2NodeConfig

    def startup_handler(self) -> None:
        """Called to (re)initialize the node. Should be used to open connections to devices or initialize any other resources."""
        self.logger.log("Node initializing...")
        temp_dir = Path.home() / ".madsci" / ".ot2_temp"
        temp_dir.mkdir(exist_ok=True)
        self.protocols_folder_path = str(
            temp_dir / self.node_definition.node_name / "protocols/"
        )
        # Create templates
        self._create_ot2_templates()

        # Create deck instance
        self.deck = self.resource_client.create_resource_from_template(
            template_name="ot2_deck",
            resource_name=f"ot2_{self.node_definition.node_name}_deck",
            add_to_database=True,
        )

        # Create 12 deck slots (1-11 standard, 12 is trash)
        for i in range(1, 13):
            slot_name = f"ot2_{self.node_definition.node_name}_deck_slot_{i}"
            template_name = "ot2_trash_slot" if i == 12 else "ot2_deck_slot"

            slot = self.resource_client.create_resource_from_template(
                template_name=template_name,
                resource_name=slot_name,
                add_to_database=True,
            )

            try:
                self.resource_client.set_child(self.deck, str(i), slot)
            except Exception:
                self.logger.log(f"Deck slot {i} already exists")

        # Create pipette mount slots
        self.pipette_slots = {}
        for mount in ["left", "right"]:
            mount_slot = self.resource_client.create_resource_from_template(
                template_name="ot2_pipette_mount",
                resource_name=f"ot2_{self.node_definition.node_name}_{mount}_mount",
                add_to_database=True,
            )
            self.pipette_slots[mount] = mount_slot

        if self.config.ot2_ip is None:
            raise ValueError("OT2 IP address is not configured.")
        try:
            self.ot2_interface = OT2_Driver(OT2_Config(ip=self.config.ot2_ip))
        except Exception as e:
            self.logger.error(f"Failed to connect to OT2: {e}")
            raise e

        self.run_id = None
        self.startup_has_run = True
        self.logger.info("OT2 node initialized!")

    def _create_ot2_templates(self) -> None:
        """Create all OT2-specific resource templates."""

        # 0. Deck container template
        deck_container = Container(
            resource_name="ot2_deck",
            resource_class="OT2Deck",
            capacity=12,
            attributes={
                "deck_type": "OT2",
                "slot_count": 12,
                "sbs_compatible": True,
                "description": "OT2 deck with 11 standard slots plus trash bin",
            },
        )

        self.resource_client.init_template(
            resource=deck_container,
            template_name="ot2_deck",
            description="Template for OT2 deck container. Holds 11 deck slots plus trash bin.",
            required_overrides=["resource_name"],
            tags=["ot2", "deck", "container"],
            created_by=self.node_definition.node_id,
            version="1.0.0",
        )

        # 1. Deck slot template (standard slots 1-11)
        deck_slot = Slot(
            resource_name="ot2_deck_slot",
            resource_class="OT2DeckSlot",
            capacity=1,
            attributes={
                "slot_type": "deck_position",
                "sbs_compatible": True,
                "description": "OT2 deck slot for labware",
            },
        )

        self.resource_client.init_template(
            resource=deck_slot,
            template_name="ot2_deck_slot",
            description="Template for OT2 deck slot. Standard SBS-compatible position.",
            required_overrides=["resource_name"],
            tags=["ot2", "deck", "slot"],
            created_by=self.node_definition.node_id,
            version="1.0.0",
        )

        # 2. Trash bin template (slot 12) - Stack type for collecting tips/waste
        trash_bin = Stack(
            resource_name="ot2_trash",
            resource_class="OT2TrashBin",
            attributes={
                "container_type": "trash_bin",
                "removable": True,
                "description": "OT2 removable trash bin at slot 12",
            },
        )

        self.resource_client.init_template(
            resource=trash_bin,
            template_name="ot2_trash_slot",
            description="Template for OT2 trash bin slot.",
            required_overrides=["resource_name"],
            tags=["ot2", "trash", "stack"],
            created_by=self.node_definition.node_id,
            version="1.0.0",
        )

        # 3. Pipette mount template
        pipette_mount = Slot(
            resource_name="ot2_pipette_mount",
            resource_class="OT2PipetteMount",
            capacity=1,
            attributes={
                "mount_type": "pipette_mount",
                "description": "OT2 pipette mount (left or right)",
            },
        )

        self.resource_client.init_template(
            resource=pipette_mount,
            template_name="ot2_pipette_mount",
            description="Template for OT2 pipette mount slot.",
            required_overrides=["resource_name"],
            tags=["ot2", "pipette", "mount", "slot"],
            created_by=self.node_definition.node_id,
            version="1.0.0",
        )

        # 4. P20 Single-Channel Pipette
        p20_single = Pool(
            resource_name="ot2_p20_single",
            resource_class="OT2_P20_Single",
            capacity=20.0,
            attributes={
                "pipette_type": "p20_single_gen2",
                "channels": 1,
                "min_volume": 1.0,
                "max_volume": 20.0,
                "accuracy_1ul": {"random_error_pct": 15.0, "systematic_error_pct": 5.0},
                "accuracy_10ul": {"random_error_pct": 2.0, "systematic_error_pct": 1.0},
                "accuracy_20ul": {"random_error_pct": 1.5, "systematic_error_pct": 0.8},
                "description": "P20 Single-Channel pipette (1-20 µL)",
            },
        )

        self.resource_client.init_template(
            resource=p20_single,
            template_name="ot2_p20_single_pipette",
            description="Template for OT2 P20 Single-Channel pipette (1-20 µL).",
            required_overrides=["resource_name"],
            tags=["ot2", "pipette", "p20", "single-channel", "pool"],
            created_by=self.node_definition.node_id,
            version="1.0.0",
        )

        # 5. P300 Single-Channel Pipette
        p300_single = Pool(
            resource_name="ot2_p300_single",
            resource_class="OT2_P300_Single",
            capacity=300.0,
            attributes={
                "pipette_type": "p300_single_gen2",
                "channels": 1,
                "min_volume": 20.0,
                "max_volume": 300.0,
                "accuracy_20ul": {"random_error_pct": 4.0, "systematic_error_pct": 2.5},
                "accuracy_150ul": {
                    "random_error_pct": 1.0,
                    "systematic_error_pct": 0.4,
                },
                "accuracy_300ul": {
                    "random_error_pct": 0.6,
                    "systematic_error_pct": 0.3,
                },
                "description": "P300 Single-Channel pipette (20-300 µL)",
            },
        )

        self.resource_client.init_template(
            resource=p300_single,
            template_name="ot2_p300_single_pipette",
            description="Template for OT2 P300 Single-Channel pipette (20-300 µL).",
            required_overrides=["resource_name"],
            tags=["ot2", "pipette", "p300", "single-channel", "pool"],
            created_by=self.node_definition.node_id,
            version="1.0.0",
        )

        # 6. P1000 Single-Channel Pipette
        p1000_single = Pool(
            resource_name="ot2_p1000_single",
            resource_class="OT2_P1000_Single",
            capacity=1000.0,
            attributes={
                "pipette_type": "p1000_single_gen2",
                "channels": 1,
                "min_volume": 100.0,
                "max_volume": 1000.0,
                "accuracy_100ul": {
                    "random_error_pct": 2.0,
                    "systematic_error_pct": 1.0,
                },
                "accuracy_500ul": {
                    "random_error_pct": 1.0,
                    "systematic_error_pct": 0.2,
                },
                "accuracy_1000ul": {
                    "random_error_pct": 0.7,
                    "systematic_error_pct": 0.15,
                },
                "description": "P1000 Single-Channel pipette (100-1000 µL)",
            },
        )

        self.resource_client.init_template(
            resource=p1000_single,
            template_name="ot2_p1000_single_pipette",
            description="Template for OT2 P1000 Single-Channel pipette (100-1000 µL).",
            required_overrides=["resource_name"],
            tags=["ot2", "pipette", "p1000", "single-channel", "pool"],
            created_by=self.node_definition.node_id,
            version="1.0.0",
        )

        # 7. P20 8-Channel Pipette
        p20_multi = Pool(
            resource_name="ot2_p20_multi",
            resource_class="OT2_P20_Multi",
            capacity=20.0,
            attributes={
                "pipette_type": "p20_multi_gen2",
                "channels": 8,
                "min_volume": 1.0,
                "max_volume": 20.0,
                "accuracy_1ul": {
                    "random_error_pct": 20.0,
                    "systematic_error_pct": 10.0,
                },
                "accuracy_10ul": {"random_error_pct": 3.0, "systematic_error_pct": 2.0},
                "accuracy_20ul": {"random_error_pct": 2.2, "systematic_error_pct": 1.5},
                "fill_96well_time_seconds": 22,
                "description": "P20 8-Channel pipette (1-20 µL)",
            },
        )

        self.resource_client.init_template(
            resource=p20_multi,
            template_name="ot2_p20_multi_pipette",
            description="Template for OT2 P20 8-Channel pipette (1-20 µL).",
            required_overrides=["resource_name"],
            tags=["ot2", "pipette", "p20", "8-channel", "multi-channel", "pool"],
            created_by=self.node_definition.node_id,
            version="1.0.0",
        )

        # 8. P300 8-Channel Pipette
        p300_multi = Pool(
            resource_name="ot2_p300_multi",
            resource_class="OT2_P300_Multi",
            capacity=300.0,
            attributes={
                "pipette_type": "p300_multi_gen2",
                "channels": 8,
                "min_volume": 20.0,
                "max_volume": 300.0,
                "accuracy_20ul": {
                    "random_error_pct": 10.0,
                    "systematic_error_pct": 4.0,
                },
                "accuracy_150ul": {
                    "random_error_pct": 2.5,
                    "systematic_error_pct": 0.8,
                },
                "accuracy_300ul": {
                    "random_error_pct": 1.5,
                    "systematic_error_pct": 0.5,
                },
                "fill_96well_time_seconds": 26,
                "description": "P300 8-Channel pipette (20-300 µL)",
            },
        )

        self.resource_client.init_template(
            resource=p300_multi,
            template_name="ot2_p300_multi_pipette",
            description="Template for OT2 P300 8-Channel pipette (20-300 µL).",
            required_overrides=["resource_name"],
            tags=["ot2", "pipette", "p300", "8-channel", "multi-channel", "pool"],
            created_by=self.node_definition.node_id,
            version="1.0.0",
        )

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
                "ot2_status_code": self.ot2_interface.get_robot_status(),
            }

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
