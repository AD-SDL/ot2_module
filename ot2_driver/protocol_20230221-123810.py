from opentrons import protocol_api

metadata = {
    "protocolName": "Color Mixing all",
    "author": "Kyle khippe@anl.gov",
    "description": "Mixing red colors",
    "apiLevel": "2.12",
}


def run(protocol: protocol_api.ProtocolContext):
    deck = {}
    pipettes = {}

    ################
    # load labware #
    ################
    deck["2"] = protocol.load_labware("corning_96_wellplate_360ul_flat", "2")
    deck["7"] = protocol.load_labware("opentrons_6_tuberack_nest_50ml_conical", "7")
    deck["10"] = protocol.load_labware("opentrons_96_tiprack_300ul", "10")
    deck["11"] = protocol.load_labware("opentrons_96_tiprack_20ul", "11")
    pipettes["left"] = protocol.load_instrument(
        "p300_single_gen2", "left", tip_racks=[deck["10"]]
    )
    pipettes["right"] = protocol.load_instrument(
        "p20_single_gen2", "right", tip_racks=[deck["11"]]
    )

    ####################
    # execute commands #
    ####################

    # Mix Color 1
    pipettes["left"].pick_up_tip(deck["10"].wells()[0])
    pipettes["left"].well_bottom_clearance.aspirate = 1.0
    pipettes["left"].aspirate(115.4762467176098, deck["7"]["A1"])
    pipettes["left"].well_bottom_clearance.dispense = 2.0
    pipettes["left"].dispense(115.4762467176098, deck["2"]["A5"])
    pipettes["left"].blow_out()
    pipettes["left"].drop_tip()

    pipettes["right"].pick_up_tip(deck["11"].wells()[0])
    pipettes["right"].well_bottom_clearance.aspirate = 1.0
    pipettes["right"].aspirate(10.798025951514752, deck["7"]["A1"])
    pipettes["right"].well_bottom_clearance.dispense = 2.0
    pipettes["right"].dispense(10.798025951514752, deck["2"]["A6"])
    pipettes["right"].blow_out()
    pipettes["right"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[1])
    pipettes["left"].well_bottom_clearance.aspirate = 1.0
    pipettes["left"].aspirate(117.21435650951516, deck["7"]["A1"])
    pipettes["left"].well_bottom_clearance.dispense = 2.0
    pipettes["left"].dispense(117.21435650951516, deck["2"]["A7"])
    pipettes["left"].blow_out()
    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[2])
    pipettes["left"].well_bottom_clearance.aspirate = 1.0
    pipettes["left"].aspirate(102.18122072599819, deck["7"]["A1"])
    pipettes["left"].well_bottom_clearance.dispense = 2.0
    pipettes["left"].dispense(102.18122072599819, deck["2"]["A8"])
    pipettes["left"].blow_out()
    pipettes["left"].drop_tip()

    # Mix color 2
    pipettes["left"].pick_up_tip(deck["10"].wells()[3])
    pipettes["left"].well_bottom_clearance.aspirate = 1.0
    pipettes["left"].aspirate(145.6764437198558, deck["7"]["A2"])
    pipettes["left"].well_bottom_clearance.dispense = 2.0
    pipettes["left"].dispense(145.6764437198558, deck["2"]["A5"])
    pipettes["left"].blow_out()
    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[4])
    pipettes["left"].well_bottom_clearance.aspirate = 1.0
    pipettes["left"].aspirate(130.2704227310534, deck["7"]["A2"])
    pipettes["left"].well_bottom_clearance.dispense = 2.0
    pipettes["left"].dispense(130.2704227310534, deck["2"]["A6"])
    pipettes["left"].blow_out()
    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[5])
    pipettes["left"].well_bottom_clearance.aspirate = 1.0
    pipettes["left"].aspirate(85.6159229289504, deck["7"]["A2"])
    pipettes["left"].well_bottom_clearance.dispense = 2.0
    pipettes["left"].dispense(85.6159229289504, deck["2"]["A7"])
    pipettes["left"].blow_out()
    pipettes["left"].drop_tip()

    pipettes["right"].pick_up_tip(deck["11"].wells()[1])
    pipettes["right"].well_bottom_clearance.aspirate = 1.0
    pipettes["right"].aspirate(14.393859964983204, deck["7"]["A2"])
    pipettes["right"].well_bottom_clearance.dispense = 2.0
    pipettes["right"].dispense(14.393859964983204, deck["2"]["A8"])
    pipettes["right"].blow_out()
    pipettes["right"].drop_tip()

    # Mix color 3
    pipettes["right"].pick_up_tip(deck["11"].wells()[2])
    pipettes["right"].well_bottom_clearance.aspirate = 1.0
    pipettes["right"].aspirate(13.847309562534427, deck["7"]["A3"])
    pipettes["right"].well_bottom_clearance.dispense = 2.0
    pipettes["right"].dispense(13.847309562534427, deck["2"]["A5"])
    pipettes["right"].mix(3, 100, deck["2"]["A5"])
    pipettes["right"].blow_out()
    pipettes["right"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[6])
    pipettes["left"].well_bottom_clearance.aspirate = 1.0
    pipettes["left"].aspirate(133.93155131743183, deck["7"]["A3"])
    pipettes["left"].well_bottom_clearance.dispense = 2.0
    pipettes["left"].dispense(133.93155131743183, deck["2"]["A6"])
    pipettes["left"].mix(3, 100, deck["2"]["A6"])
    pipettes["left"].blow_out()
    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[7])
    pipettes["left"].well_bottom_clearance.aspirate = 1.0
    pipettes["left"].aspirate(72.16972056153442, deck["7"]["A3"])
    pipettes["left"].well_bottom_clearance.dispense = 2.0
    pipettes["left"].dispense(72.16972056153442, deck["2"]["A7"])
    pipettes["left"].mix(3, 100, deck["2"]["A7"])
    pipettes["left"].blow_out()
    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[8])
    pipettes["left"].well_bottom_clearance.aspirate = 1.0
    pipettes["left"].aspirate(158.4249193090186, deck["7"]["A3"])
    pipettes["left"].well_bottom_clearance.dispense = 2.0
    pipettes["left"].dispense(158.4249193090186, deck["2"]["A8"])
    pipettes["left"].mix(3, 100, deck["2"]["A8"])
    pipettes["left"].blow_out()
    pipettes["left"].drop_tip()
