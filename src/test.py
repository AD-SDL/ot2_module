from madsci.client.resource_client import ResourceClient
from madsci.common.types.resource_types import Asset, Consumable, Grid
from madsci.common.types.resource_types.definitions import ResourceDefinition

import json

client = ResourceClient("http://localhost:8003")


def parse_logfile(ot_log):
    """Master function, parses opentrons logfile and updates resources accordingly"""

    with open(ot_log, 'r') as file:
        log = json.load(file)
        print(log['commands']['data'][1]['commandType'])
        print(len(log['commands']['data']))
        for i in range(log['commands']['data']):
            #TODO add full suite of commandTypes
            if log['commands']['data'][i]['commandType'] == "loadLabware":
                pass
            elif log['commands']['data'][i]['commandType'] == "home":
                pass
            elif log['commands']['data'][i]['commandType'] == "loadPipette":
                pass
            elif log['commands']['data'][i]['commandType'] == "pickUpTip":
                pass
            elif log['commands']['data'][i]['commandType'] == "aspirate":
                pass
            elif log['commands']['data'][i]['commandType'] == "dispense":
                pass
            elif log['commands']['data'][i]['commandType'] == "dropTip":
                pass
    

def aspirate():
    pass

def dispense():
    pass

def pick_up_tip():
    pass

def drop_tip():
    pass


example = "example_log.json"

parse_logfile(example)