from opentrons import protocol_api
import itertools
from opentrons.protocol_api import SINGLE


metadata = {
    'protocolName': 'Protein Design Golden Gate 81 reagents for the OT-2',
    'author': 'LDRD team ',
    'description': 'Golden Gate Assembly for Protein Design 81 combinations',
    'source': 'FlexGB/ProteinDesign/pd_golden_gate_81_ot2.py',
}

requirements = {"robotType": "OT-2", "apiLevel": "2.20"}


# Protocol Configuration
config = {
    # Combinatorial mixing
    'combinations': [[18,10,2],[11,19,3],[4,20,12],[21,13,5]],
    # gbabnigg.changes.start
    'use_combinations': False,
    # the below 2D array defines which source wells to combine for each destination well
    # 2025-11-03.example    
    'non_combinatorial_sources': [
        # [1,2,3,4],
        # [9,2,3,12],
        # [9,10,3,4],
        # [9,10,3,12],
        # [9,10,11,12],
        # [9,18,3,4],
        # [17,18,19,4],
        # [17,18,19,20],

        [1,2,3,4],
        [9,2,3,12],
        [9,10,3,4],
        [9,10,3,12],
        [9,10,11,12],
        [9,18,3,4],
        [17,18,19,4],
        [17,18,19,20],

        [1,2,3,4],
        [9,2,3,12],
        [9,10,3,4],
        [9,10,3,12],
        [9,10,11,12],
        [9,18,3,4],
        [17,18,19,4],
        [17,18,19,20]
    ],
    # gbabnigg.changes.end
    'transfer_volume': 2.5,  # µL from each source well
    'aspirate_transfer_volume': 5.5,
    'dispense_transfer_volume': 5,

    # Master mix settings
    'master_mix_volume': 12,  # µL per destination well
    'master_mix_well_volume': 100,  # µL per master mix well
    'master_mix_start_well': 32,  # 0-indexed well number

    # Temperature settings
    'temperature': 4,  # °C

    # Labware
    'fragments_plate_type': 'opentrons_96_wellplate_200ul_pcr_full_skirt', # nest_96_wellplate_100ul_pcr_full_skirt
    'gg_plate_type': 'opentrons_96_wellplate_200ul_pcr_full_skirt', # nest_96_wellplate_100ul_pcr_full_skirt
    'tip_rack_type_50_01': 'opentrons_96_filtertiprack_20ul',
    'tip_rack_type_50_02': 'opentrons_96_filtertiprack_20ul',
    'tip_rack_type_50_03': 'opentrons_96_filtertiprack_20ul',
    'tip_rack_type_50_04': 'opentrons_96_filtertiprack_20ul',
    'tip_rack_type_50_05': 'opentrons_96_filtertiprack_20ul',
    'pipette_type_20': 'p20_single',
    # 'tip_rack_type_200_01': 'opentrons_flex_96_tiprack_200ul',
    'pipette_type_1000': 'flex_8channel_1000',

    # Deck positions
    'temp_module_01_position': 'B1',
    'temp_module_02_position': 'C1',
    'fragments_plate_initial_position': 'B1',
    'gg_plate_position': 'C1',
    'tip_rack_position_50_01': 'A2',
    'tip_rack_position_50_02': 'A3',
    'tip_rack_position_50_03': 'B2',
    'tip_rack_position_50_04': 'B3',
    'tip_rack_position_50_05': 'C3',
    # 'tip_rack_position_200_01': 'A2',
    'reagent_block': 'A1'
}


def calculate_total_combinations(combinations):
    """Calculate total number of combinations without generating them"""
    total = 1
    for sublist in combinations:
        total *= len(sublist)
    return total

def generate_all_combinations(combinations):
    """Generate all possible combinations from the jagged array"""
    return list(itertools.product(*combinations))

def transfer_combinatorial_liquids(protocol, source_plate, dest_plate, pipette, config):
    """
    Transfer liquids based on combinatorial mixing pattern

    Args:
        protocol: Opentrons protocol object
        source_plate: Source PCR plate labware
        dest_plate: Destination PCR plate labware
        pipette: Pipette instrument
        config: Configuration dictionary containing combinations and transfer_volume
    """

    
    transfer_volume = config['transfer_volume']
    #reverse pipetting values
    aspirate_transfer_volume = config['aspirate_transfer_volume']
    dispense_transfer_volume = config['dispense_transfer_volume']

    # Calculate total combinations before generating them

    # gbabnigg.changes.start

    combinations = None
    total_combinations = 0
    all_combinations = None
    if  config['use_combinations'] is True:
        combinations = config['combinations']
        total_combinations = calculate_total_combinations(combinations)
        # Generate all possible combinations
        all_combinations = generate_all_combinations(combinations)
    else:
        all_combinations = config['non_combinatorial_sources']
        total_combinations = len(all_combinations)
    # gbabnigg.changes.end
    protocol.comment(f"Total destination wells needed: {total_combinations}")



    print(f"Generated {len(all_combinations)} combinations:")
    for i, combo in enumerate(all_combinations):
        print(f"Destination well {i+1}: Sources {combo}")

    # Perform transfers
    dest_well_number = 9

    for combination in all_combinations:
        # For each combination, transfer from all source wells to one destination well
        dest_well = dest_plate.wells()[dest_well_number - 1]  # Convert to 0-based index

        protocol.comment(f"\nTransferring to destination well {dest_well_number}:")

        for idx, source_well_number in enumerate(combination):
            source_well = source_plate.wells()[source_well_number - 1]  # Convert to 0-based index

            protocol.comment(f"  - Transferring {transfer_volume}µL from source well {source_well_number} to dest well {dest_well_number}")

            # Pick up tip for transfer
            pipette.pick_up_tip()
            
            # Aspirate from source
            #default flow rate is 35
            # pipette.flow_rate.aspirate = 18
            pipette.aspirate(aspirate_transfer_volume, source_well)
            
            # Dispense to destination
            pipette.flow_rate.dispense = 29
            pipette.dispense(dispense_transfer_volume, dest_well)
            
            # Blow out after dispensing
            # pipette.blow_out(dest_well)
            pipette.drop_tip()
            
            # Check if this is the last member of the combination
            #TODO: mixing temporarily removed
            if idx == len(combination) - 1:
                pipette.pick_up_tip()
                protocol.comment(f"  - Mixing in destination well {dest_well_number} after last transfer")
                # Mix using the same tip
                pipette.mix(repetitions=3, volume=transfer_volume * len(combination) * 0.7, location=dest_well, rate=0.2)
                # pipette.blow_out(dest_well)
                pipette.drop_tip()
            # Drop tip
            # pipette.drop_tip()
            
        dest_well_number += 1

def add_master_mix_to_combinations(protocol, source_plate, dest_plate, pipette, config):
    """
    Add master mix to each destination well after combinatorial transfers

    Args:
        protocol: Opentrons protocol object
        source_plate: Source PCR plate labware (contains master mix)
        dest_plate: Destination PCR plate labware
        pipette: Pipette instrument
        config: Configuration dictionary containing master mix settings
    """

    combinations = config['combinations']
    master_mix_volume = config['master_mix_volume']
    master_mix_well_volume = config['master_mix_well_volume']
    master_mix_start_well = config['master_mix_start_well']

    # Calculate total combinations
    total_combinations = calculate_total_combinations(combinations)

    # Calculate how many destination wells can be served by one master mix well
    dispenses_per_well = master_mix_well_volume // master_mix_volume
    protocol.comment(f"Each master mix well ({master_mix_well_volume}µL) can serve {dispenses_per_well} destination wells")

    # Calculate how many master mix wells we need
    master_mix_wells_needed = (total_combinations + dispenses_per_well - 1) // dispenses_per_well  # Ceiling division
    protocol.comment(f"Total master mix wells needed: {master_mix_wells_needed}")

    # Track current master mix well and remaining volume
    current_master_mix_well = master_mix_start_well
    remaining_dispenses = dispenses_per_well + 1

    protocol.comment(f"\nAdding {master_mix_volume}µL master mix to each destination well:")

    for dest_well_number in range(1, total_combinations + 1):
        # Check if we need to switch to next master mix well
        if remaining_dispenses == 0:
            current_master_mix_well += 1
            remaining_dispenses = dispenses_per_well
            protocol.comment(f"  Switching to master mix well {current_master_mix_well + 1} (0-indexed: {current_master_mix_well})")

        # Get the destination well
        dest_well = dest_plate.wells()[dest_well_number - 1]  # Convert to 0-based index

        # Get the current master mix well
        master_mix_well = source_plate.wells()[current_master_mix_well]

        protocol.comment(f"  Dest well {dest_well_number}: Adding {master_mix_volume}µL from master mix well {current_master_mix_well + 1} (0-indexed: {current_master_mix_well})")

        # Transfer master mix
        pipette.transfer(
            master_mix_volume,
            master_mix_well,
            dest_well,
            new_tip='always'  # Use fresh tip for each master mix transfer
        )

        # Update remaining dispenses
        remaining_dispenses -= 1

    protocol.comment(f"\nMaster mix addition complete. Used wells {master_mix_start_well + 1} to {current_master_mix_well + 1} (0-indexed: {master_mix_start_well} to {current_master_mix_well})")

    return current_master_mix_well  # Return the last used well




def run(protocol: protocol_api.ProtocolContext):
    # Load temperature module and adapter
    temp_mod_1 = protocol.load_module(module_name="temperature module gen2", location=config['temp_module_01_position'])
    temp_mod_2 = protocol.load_module(module_name="temperature module gen2", location=config['temp_module_02_position'])

    temp_adapter_1 = temp_mod_1.load_adapter("opentrons_96_well_aluminum_block")
    temp_adapter_2 = temp_mod_2.load_adapter("opentrons_96_well_aluminum_block")

    # Set temperature
    temp_mod_1.set_temperature(config['temperature']) #TODO: make seperate, or just set earlier, only 1 hour with plate
    temp_mod_2.set_temperature(config['temperature'])
    # Load source plate initially on A4
    # source_plate = protocol.load_labware(config['source_plate_type'], config['source_plate_initial_position'])
    source_plate = temp_adapter_1.load_labware(config['fragments_plate_type'])

    # Move source plate to temperature module
    # protocol.move_labware(
    #     labware=source_plate,
    #     new_location=temp_adapter,
    #     use_gripper=True
    # )

    chute = protocol.load_waste_chute()

    # source_plate.set_offset(x=0.40, y=0.50, z=2.40)
    # source_plate.set_offset(x=0.7, y=0.30, z=0.2)
    source_plate.set_offset(x=0.0, y=0.80, z=-1.5)


    # Load destination plate
    # dest_plate = protocol.load_labware(config['gg_plate_type'], config['gg_plate_position'])
    dest_plate = temp_adapter_2.load_labware(config['gg_plate_type'])
    # dest_plate.set_offset(x=0.4, y=0.4, z=0.0)
    dest_plate.set_offset(x=0.0, y=0.8, z=-1.5)

    tiprack_50_1 = protocol.load_labware(
        load_name=config['tip_rack_type_50_01'], location=config['tip_rack_position_50_01']
    )
    tiprack_50_2 = protocol.load_labware(
        load_name=config['tip_rack_type_50_02'], location=config['tip_rack_position_50_02']
    )
    tiprack_50_3 = protocol.load_labware(
        load_name=config['tip_rack_type_50_03'], location=config['tip_rack_position_50_03']
    )
    tiprack_50_4 = protocol.load_labware(
        load_name=config['tip_rack_type_50_04'], location=config['tip_rack_position_50_04']
    )
    tiprack_50_5 = protocol.load_labware(
        load_name=config['tip_rack_type_50_05'], location=config['tip_rack_position_50_05']
    )

    # # 8-channel P1000
    # tiprack_200 = protocol.load_labware(
    #     load_name=config['tip_rack_type_200_01'], location=config['tip_rack_position_200_01']
    # )

    # Pipettes
    # p50 = protocol.load_instrument('flex_8channel_50', mount='right', tip_racks=[tiprack_50_1, tiprack_50_2, tiprack_50_3, tiprack_50_4, tiprack_50_5])
    p50s = protocol.load_instrument('pipette_type_20', mount='left', tip_racks=[tiprack_50_1, tiprack_50_2, tiprack_50_3, tiprack_50_4, tiprack_50_5])

    # p50.configure_nozzle_layout(style=SINGLE, start='A1', tip_racks=[tiprack_50_1, tiprack_50_2, tiprack_50_3, tiprack_50_4, tiprack_50_5])
    # p50s.configure_nozzle_layout(style=SINGLE, start='A1', tip_racks=[tiprack_50_1, tiprack_50_2, tiprack_50_3, tiprack_50_4, tiprack_50_5])



    # Perform combinatorial transfers #TODO: SWAP?  so adding small vols into large quant of master mix
    total_dest_wells = transfer_combinatorial_liquids(
        protocol=protocol,
        source_plate=source_plate,
        dest_plate=dest_plate,
        pipette=p50s,
        config=config
    )

    # Add master mix to each destination well
    # last_master_mix_well = add_master_mix_to_combinations(
    #     protocol=protocol,
    #     source_plate=source_plate,
    #     dest_plate=dest_plate,
    #     pipette=p50s,
    #     config=config
    # )
