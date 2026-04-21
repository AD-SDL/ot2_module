#!/usr/bin/env python3
"""Experiment application for the Protein Design experiment"""

import time
from datetime import datetime
from pathlib import Path

from madsci.common.types.experiment_types import ExperimentDesign
from madsci.client import ExperimentClient, WorkcellClient, LocationClient, ResourceClient
from madsci.common.types.node_types import NodeDefinition
from madsci.common.types.resource_types import Resource
from madsci.experiment_application import (
    ExperimentApplication,
    ExperimentApplicationConfig,
)
from pydantic import AnyUrl

# import helper_functions





class PDApp(ExperimentApplication):
    """PD Experiment Application

    # TODO:

    """

    experiment_design = ExperimentDesign(
        experiment_name="PD_App",
    )
    config = ExperimentApplicationConfig(node_url=AnyUrl("http://localhost:6000"))
    experiment_client = ExperimentClient()
    workcell_client = WorkcellClient()
    location_client = LocationClient()
    resource_client = ResourceClient()
    experiment_id = None
    experiment_label = None


    def __init__(self) -> None:
        """Initializes the PD Experiment App"""

        super().__init__()
        self.init_assay_plate_resource_template()

    def init_assay_plate_resource_template(self):
        """Initializes assay plate resource template"""

        self.resource_client.create_template(
            resource=Resource(
                resource_description="NEST PCR plate 200ul",
            ),
            template_name="opentrons_96_wellplate_200ul_pcr_full_skirt",
            description="Template for 200ul PCR plate",
            tags=["Plate", "ANSI/SLAS", "96 Well", "PCR", "Labware"],
        )

        self.resource_client.create_template(
            resource=Resource(
                resource_description="ot2 20ul tiprack",
            ),
            template_name="opentrons_96_filtertiprack_20ul",
            description="Template for ot2 20ul tiprack",
            tags=["Tiprack", "ANSI/SLAS", "96 Well", "Labware"],
        )

        self.resource_client.create_template(
            resource=Resource(
                resource_description="otflex 50ul tiprack",
            ),
            template_name="opentrons_flex_96_filtertiprack_50ul",
            description="Template for OT-Flex 50ul tiprack",
            tags=["Tiprack", "ANSI/SLAS", "96 Well", "Labware"],
        )

        self.resource_client.create_template(
            resource=Resource(
                resource_description="otflex 200ul tiprack",
            ),
            template_name="opentrons_flex_96_filtertiprack_200ul",
            description="Template for 200ul OT-Flex tiprack",
            tags=["Tiprack", "ANSI/SLAS", "96 Well", "Labware"],
        )


    def push_new_assay_plate_resource(
            self,
            plate_num: int,
            location_name: str,
            experiment_id: int,
            name: str,
        ) -> None | Resource:
            """
            Pushes a new assay plate resource into the specified location, popping an existing plate in that location if necessary.
            """
            # get the resource id of the resource associated with the given location
            associated_resource_id = self.location_client.get_location_by_name(location_name).resource_id
            print("Location name: ", location_name)
            print("ASSC Resource id: ", associated_resource_id)
            # get the resource object from the resource id
            resource_object = self.resource_client.get_resource(associated_resource_id)

            # check if the resource object currently has child resources (a plate already at that location)
            old_plate = None
            if resource_object.child:
                    # there is already a plate at this location
                    self.logger.log_info(f"A plate with ID {resource_object.child.resource_id} already exists at location: {location_name}")

                    # pop the old plate
                    popped_plate, updated_parent = self.resource_client.pop(resource=associated_resource_id)
                    self.logger.log_info(f"Popped plate with ID {resource_object.child.resource_id} from location: {location_name}")
                    old_plate = popped_plate


            # create a new assay plate resource and push it into the resource object associated with the given location
            # if name == "opentrons_96_wellplate_200ul_pcr_full_skirt":

            new_plate = self.resource_client.create_resource_from_template(
                template_name = name,
                resource_name = f"res_{experiment_id}_plate{plate_num}",
            )

            self.logger.log_info(f"Created new plate resource {new_plate.resource_name}, {new_plate.resource_id}")

            self.resource_client.push(
                resource = associated_resource_id,
                child = new_plate.resource_id,
            )
            self.logger.log_info(f"Pushed new plate resource into location {location_name}")
            return new_plate, old_plate

    def run_experiment(self) -> None:
        """main experiment function"""

        #TODO: plate starting on ot2 patrick deck 6 on temp block
        # new_plate, old_plate = self.push_new_assay_plate_resource(
        #         location_name="ot2_patrick_nest6_temp_block_wide",
        #     )

        # DEFINE PATHS AND VARIABLES ========
        run_robots = False  # if False, no robots will run
        run_resources = True
        test_prints = True  # if True, will print out extra info for testing purposes

        # Experiment ID and name
        experiment_id = self.experiment.experiment_id
        experiment_label = "1"

        # Directory paths
        app_directory = Path(__file__).parent.parent   # experiment app
        wf_directory = app_directory / "workflows"  # workflows
        run_directory = wf_directory / "run_instrument"
        transfers_directory = wf_directory / "transfers"
        protocol_directory = app_directory / "protocols"    # protocols

        # Workflow paths
        run_ot2_wf = "run_ot2_wf.yaml"
        run_thermo_wf = run_directory / "run_thermo.yaml"

        ot2_to_thermocycler = (
            transfers_directory / "ot2_to_thermocycler.yaml"
        )


        # Protocol paths (for OT-2)
        golden_gate_protocol = protocol_directory / "pd_golden_gate_ot2_v2.py"

        seal_and_thermocycle = (
             transfers_directory / "seal_and_thermocycle_pcr.yaml"
        )

        payload = {}

        temp_ot2_file_str = "basic_config_alpha.py"

        # combination_data = self.rest_handler.collect_combinations(oracle_id=1008)
        # print("combination_data", combination_data)
        # print(combination_data["combinations"])
        # print(combination_data["use_combinations"])
        # print(combination_data["non_combinatorial_sources"])

        # payload["combinations"] = combination_data["combinations"]
        # payload["use_combinations"] = combination_data["use_combinations"]
        # payload["non_combinatorial_sources"] = combination_data["non_combinatorial_sources"]



        # EXPERIMENT ACTIONS -------------------------------------------------------

        # run ot2 protocol step 1
        # ot2_replacement_variables = helper_functions.collect_ot2_replacement_variables(payload)
        # temp_ot2_file_str = helper_functions.generate_ot2_protocol(golden_gate_protocol, ot2_replacement_variables)
        payload["current_ot2_protocol"] = temp_ot2_file_str
        workflow = self.workcell_client.submit_workflow(
            run_ot2_wf.resolve(),
            file_inputs={
                "ot2_protocol": payload["current_ot2_protocol"],
            },
        )

###### depending on combinatorial length, will need additional tips
        #swap tip boxes

        #run ot2 protocol step 2

        #swap tip boxes

        #run ot2 protocol step 3 with master mix multi dispense

        #########################

        # transfer destination plate to thermocycler and run
        # workflow = self.workcell_client.submit_workflow(
        #     seal_and_thermocycle.resolve(),
        # )

        # #run thermocycler
        # workflow = self.workcell_client.submit_workflow(
        #     run_thermo_wf.resolve(),
        # )





if __name__ == "__main__":
    exp_app = PDApp()

    current_time = datetime.now()

    # Start experiment run
    with exp_app.manage_experiment(
        run_name = f"PD_Experiment{current_time.strftime('%Y%m%d_%H%M%S')}",
        run_description = "PD experiment",
    ):
        exp_app.start_app()