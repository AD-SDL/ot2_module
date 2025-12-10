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
        params = command.get('params', {})
        result = command.get('result', {})

        pipette_id = result.get('pipetteId', params.get('pipetteId'))
        mount = params.get('mount', 'unknown')
        pipette_name = params.get('pipetteName', 'unknown')

        #store pipette info
        self.pipette_id_to_info[pipette_id] = {
            'pipette_id': pipette_id,
            'mount': mount,
            'pipette_name': pipette_name
        }

        #TODO: pipette = Pool?
        if mount in self.pipette_slots:
            mount_resource = self.pipette_slots[mount]

            try:
                if 'p20' in pipette_name.lower():
                    capacity = 20.0
                elif 'p300' in pipette_name.lower():
                    capacity = 300.0
                elif 'p1000' in pipette_name.lower():
                    capacity = 1000.0
                #TODO: error handling
                else:
                    capacity = 0.0
                
                pipette_resource = Pool(
                    resource_name=f"{self.node_name}_{pipette_name}_{mount}",
                    resource_class="pipette",
                    capacity=capacity,
                    attributes={
                        "ot2_pipette_id": pipette_id,
                        "pipette_name": pipette_name,
                        "mount": mount
                    }
                )   
                pipette_resource = self.client.add_resource(pipette_resource)
                self.client.set_child(resource=mount_resource, key='pipette', child=pipette_resource)
                self.pipette_id_to_resource[pipette_id] = pipette_resource
            
            except Exception as e:
                error_msg = f"Could not create pipette resource for {pipette_id}: {str(e)}"
                print(f"Warning: {error_msg}")


    def well_name_to_grid_key(self, well_name):
        """convert well name (B6 etc) to row, col format"""

        #TODO: error handling
        if not well_name:
            return (0, 0)
        
        row_letter = well_name[0].upper()
        col_number = int(well_name[1:]) if len(well_name) > 1 else 1
        
        # Convert to 0-indexed
        row_index = ord(row_letter) - ord('A')
        col_index = col_number - 1
        
        return (row_index, col_index)
    
    def pick_up_tip(self, command, ot_log):
        """handle pick up tip command"""

        params = command.get('params', {})
        labware_id = params.get('labwareId')
        well_name = params.get('wellName')

        if labware_id in self.labware_id_to_resource:
            tip_rack = self.labware_id_to_resource[labware_id]

            if isinstance(tip_rack, Grid):
                #mark tip as removed
                try:
                    grid_key = self.well_name_to_grid_key(well_name)

                    #try to get tip at location, remove it from grid
                    try:
                        tip = tip_rack.get_child(grid_key)
                        if tip:
                            #remove tip from rack
                            tip_rack.remove_child(grid_key)
                            self.client.update_resource(tip_rack)
                    except:
                        #TODO: no tip there, error handling
                        pass
                
                except Exception as e:
                    error_msg = f"error consuming tip at {well_name}: {str(e)}"
                    print(f"Warning: {error_msg}")
            
    
    def aspirate(self, command, ot_log):
        """handle aspirate command"""
        
        params = command.get('params', {})

        labware_id = params.get('labwareID')
        well_name = params.get('wellName')
        volume = params.get('volume', 0.0)

        if labware_id in self.labware_id_to_resource:
            source_labware = self.labware_id_to_resource[labware_id]

            #get liquid from given well
            if isinstance(source_labware, Grid):
                try:
                    grid_key = self.well_name_to_grid_key(well_name)
                    well_contents = source_labware.get_child(grid_key)

                    #if well contains a consumable, decrease quantity
                    if well_contents and isinstance(well_contents, Consumable):
                        self.client.decrease_quantity(resource=well_contents, amount=volume) 
                
                except Exception as e:
                    #TODO: error handling, empty well?
                    error_msg = f"error consuming tip at {well_name}: {str(e)}"
                    print(f"Warning: {error_msg}")
                    

    def dispense(self, command, ot_log):
        """handle dispense command"""
        params = command.get('params', {})
        
        labware_id = params.get('labwareId')
        well_name = params.get('wellName')
        volume = params.get('volume', 0.0)

        if labware_id in self.labware_id_to_resource:
            dest_labware = self.labware_id_to_resource[labware_id]
            
            # For Grid resources (plates), try to get the sample/liquid at this well
            if isinstance(dest_labware, Grid):
                try:
                    grid_key = self._well_name_to_grid_key(well_name)
                    well_contents = dest_labware.get_child(grid_key)
                    
                    # If the well contains a Consumable resource, increase its quantity
                    if well_contents and isinstance(well_contents, Consumable):
                        self.client.increase_quantity(resource=well_contents, amount=volume)
                
                except Exception as e:
                    error_msg = f"error dispensing at {well_name}: {str(e)}"
                    print(f"Warning: {error_msg}")

                    

    def drop_tip(self, command, ot_log):
        """handle drop tip command"""
        params = command.get('params', {})
        labware_id = params.get('labwareId')
        well_name = params.get('wellName')
        
        # most tips dropped in trash (slot 12), so no tracking?? #TODO
        #TODO: return tips to rack functionality









