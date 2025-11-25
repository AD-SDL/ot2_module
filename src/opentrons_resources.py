# from madsci.client.resource_client import ResourceClient
# from madsci.common.types.resource_types import Asset, Consumable, Grid
# from madsci.common.types.resource_types.definitions import ResourceDefinition

# import json



# class Opentrons_Resources:
#     client = ResourceClient("http://localhost:8003")
#     client.get_resource("DECK1")
#     def parse_logfile(ot_log):
#         """Master function, parses opentrons logfile and updates resources accordingly"""

#         with open(ot_log, 'r') as file:
#             log = json.load(file)
#             print(log['commands']['data'][1]['commandType'])
#             print(len(log['commands']['data']))
#             for i in range(log['commands']['data']):
#                 #TODO add full suite of commandTypes
#                 if log['commands']['data'][i]['commandType'] == "loadLabware":
#                     pass
#                 elif log['commands']['data'][i]['commandType'] == "home":
#                     pass
#                 elif log['commands']['data'][i]['commandType'] == "loadPipette":
#                     pass
#                 elif log['commands']['data'][i]['commandType'] == "pickUpTip":
#                     pass
#                 elif log['commands']['data'][i]['commandType'] == "aspirate":
#                     pass
#                 elif log['commands']['data'][i]['commandType'] == "dispense":
#                     pass
#                 elif log['commands']['data'][i]['commandType'] == "dropTip":
#                     pass
#     def aspirate(source, pipette):
#         pass

#     def dispense(destination, pipette):
#         pass

#     def pick_up_tip(source, pipette):
#         pass

#     def drop_tip(pipette):
#         pass



import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from madsci.client.resource_client import ResourceClient
from madsci.common.types.resource_types import Asset, Consumable, Grid, Pool, Container
from madsci.common.types.resource_types.definitions import ResourceDefinition

class Opentrons_Resources:
    def __init__(self):
        """
        Initialize the Opentrons Resources manager
        """
        self.client = ResourceClient("http://localhost:8003")
        self.deck_slots: Dict[str, Any] #map slot numbers to resources
        self.pipette_slots: Dict[str, Any]
        self.node_name: str
        
        # dicts for mapping OT2 labware IDs to MADSci resources
        self.labware_id_to_resource: Dict[str, Any] = {}
        self.labware_id_to_info: Dict[str, Dict] = {}
        
        # dicts for pipette resources
        self.pipette_id_to_resource: Dict[str, Any] = {}
        self.pipette_id_to_info: Dict[str, Dict] = {}
        

    def parse_logfile(self, ot_log):
        """Master function, parses opentrons logfile and updates resources accordingly"""
        log_path = Path(ot_log)
        if not log_path.exists():
            raise FileNotFoundError(f"Log file not found: {log_path}")
        
        with open(log_path, 'r') as file:
            ot_log = json.load(file)
        
        #two passes, one for all "load labware" commands, and one for all actions

        self.process_setup_commands(ot_log)
        
        self.process_protocol_commands(ot_log)
    
    def process_setup_commands(self, ot_log):
        """process setup commands (loadLabware, loadPipette)"""
        commands = ot_log.get('commands', {}).get('data', [])

        for command in commands:
            cmd_type = command.get('commandType')
            
            if cmd_type == 'loadLabware':
                self.load_labware(command, ot_log)
            elif cmd_type == 'loadPipette':
                self.load_pipette(command, ot_log)



    def process_protocol_commands(self, ot_log):
        """process protocol actions"""
        commands = ot_log.get('commands', {}).get('data', [])
        
        for command in commands:
            cmd_type = command.get('commandType')
            
            try:
                if cmd_type == 'pickUpTip':
                    self.pick_up_tip(command, ot_log)
                elif cmd_type == 'aspirate':
                    self.aspirate(command, ot_log)
                elif cmd_type == 'dispense':
                    self.dispense(command, ot_log)
                elif cmd_type == 'dropTip':
                    self.drop_tip(command, ot_log)
            except Exception as e:
                error_msg = f"Error processing {cmd_type} at {command.get('id', 'unknown')}: {str(e)}"
                print(f"Warning: {error_msg}")

    def load_labware(self, command, ot_log):
        """loads labware, tracks labware present in each deck slot"""
        params = command.get('params', {})
        result = command.get('result', {})

        #get labware id
        location = params.get(location, {})
        #labware TYPE
        load_name = params.get('loadName', 'unknown')
        #string number 1-11
        slot_name = location.get('slotName', 'unknown')

        #find matching id
        labware_id = None
        display_name = load_name
        for labware in ot_log.get('data', {}).get('labware', []):
            if (labware.get('loadName') == load_name and
                labware.get('location', {}).get('slotName') == slot_name):
                labware_id = labware.get('id')
                break
        
        if not labware_id:
            #just in case not found
            labware_id = f"labware_{slot_name}_{load_name}"
        
        slot_name = location.get('slotName', 'unknown')


        #store info
        self.labware_id_to_info[labware_id] = {
            'load_name': load_name,
            'display_name': display_name,
            'slot': slot_name,
            'labware_id': labware_id,
            'location': location
        }

        #get or create labware in deck slot
        if slot_name in self.deck_slots:
            slot_resource = self.deck_slots[slot_name]
            try:
               #check if slot already has labware (child)
               # query for existing labware in slot

               # Grid resource if tip rack
                if 'tip' in load_name.lower():
                   #tip rack always 8x12 grid
                   labware_resource = Grid(
                       resource_name = f"{self.node_name}_{display_name}_{slot_name}",
                       resource_class = "tip_rack",
                       rows = 8,
                       columns = 12,
                       attributes = {
                           "ot2_labware_id": labware_id,
                           "load_name": load_name,
                           "slot": slot_name
                       }
                   )
                   labware_resource = self.client.add_resource(labware_resource)


                   #set as child of the deck slot
                   self.client.set_child(resource=slot_resource, key="labware", child=labware_resource)
                   self.labware_id_to_resource[labware_id] = labware_resource

                elif 'plate' in load_name.lower() or 'well' in load_name.loawer():
                   #plate as grid, either 96 or 384
                    if '96' in load_name:
                       rows, cols = 8, 12
                    elif '384' in load_name:
                        rows, cols = 16, 24
                    
                    else:
                        rows, cols = 8, 12 #96 well by default
                    
                    labware_resource = Grid(
                        resource_name=f"{self.node_name}_{display_name}_{slot_name}",
                        resource_class="plate",
                        rows=rows,
                        columns=cols,
                        attributes={
                            "ot2_labware_id": labware_id,
                            "load_name": load_name,
                            "slot": slot_name
                        }
                    )
                    labware_resource = self.client.add_resource(labware_resource)
                    self.client.set_child(resource=slot_resource, key="labware", child=labware_resource)
                    self.labware_id_to_resource[labware_id] = labware_resource
                
                else:
                    #TODO: add addional labware types, tuberacks and modules etc, generic container for now
                    labware_resource = Container(
                        resource_name=f"{self.node_name}_{display_name}_{slot_name}",
                        resource_class="labware",
                        capacity=100,  # Generic capacity
                        attributes={
                            "ot2_labware_id": labware_id,
                            "load_name": load_name,
                            "slot": slot_name
                        }
                    )
                    labware_resource = self.client.add_resource(labware_resource)
                    self.client.set_child(resource=slot_resource, key="labware", child=labware_resource)
                    self.labware_id_to_resource[labware_id] = labware_resource
                   
            except Exception as e:
                error_msg = f"Could not create labware resource for {labware_id}: {str(e)}"
                print(f"Warning: {error_msg}")
        
        
    def load_pipette(self, command, ot_log):
        pass

