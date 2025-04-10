requirements = {"robotType": "OT-2"}

from opentrons import protocol_api

metadata = {
    "protocolName": "rpl demo",
    "author": "Abe astroka@anl.gov",
    "description": "demonstrates ot2 for rpl demo",
    "apiLevel": "2.12",
}


def run(protocol: protocol_api.ProtocolContext):
    deck = {}
    pipettes = {}

    ################
    # load labware #
    ################
    deck["1"] = protocol.load_labware("nest_96_wellplate_2ml_deep", "1")

    deck["4"] = protocol.load_labware("nest_96_wellplate_2ml_deep", "4")

    deck["10"] = protocol.load_labware("opentrons_96_tiprack_20ul", "10")

    pipettes["left"] = protocol.load_instrument(
        "p20_single_gen2", "left", tip_racks=[deck["10"]]
    )

    ####################
    # execute commands #
    ####################

    # Step one
    pipettes["left"].pick_up_tip(deck["10"].wells()[0])

    pipettes["left"].well_bottom_clearance.aspirate = 1.0

    pipettes["left"].aspirate(20.0, deck["4"]["A1"])

    pipettes["left"].well_bottom_clearance.dispense = 1.0

    pipettes["left"].dispense(20.0, deck["1"]["A1"])

    pipettes["left"].blow_out()

    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[1])

    pipettes["left"].well_bottom_clearance.aspirate = 1.0

    pipettes["left"].aspirate(20.0, deck["4"]["A2"])

    pipettes["left"].well_bottom_clearance.dispense = 1.0

    pipettes["left"].dispense(20.0, deck["1"]["A2"])

    pipettes["left"].blow_out()

    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[2])

    pipettes["left"].well_bottom_clearance.aspirate = 1.0

    pipettes["left"].aspirate(20.0, deck["4"]["A3"])

    pipettes["left"].well_bottom_clearance.dispense = 1.0

    pipettes["left"].dispense(20.0, deck["1"]["A3"])

    pipettes["left"].blow_out()

    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[3])

    pipettes["left"].well_bottom_clearance.aspirate = 1.0

    pipettes["left"].aspirate(20.0, deck["4"]["A4"])

    pipettes["left"].well_bottom_clearance.dispense = 1.0

    pipettes["left"].dispense(20.0, deck["1"]["A4"])

    pipettes["left"].blow_out()

    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[4])

    pipettes["left"].well_bottom_clearance.aspirate = 1.0

    pipettes["left"].aspirate(20.0, deck["4"]["A5"])

    pipettes["left"].well_bottom_clearance.dispense = 1.0

    pipettes["left"].dispense(20.0, deck["1"]["A5"])

    pipettes["left"].blow_out()

    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[5])

    pipettes["left"].well_bottom_clearance.aspirate = 1.0

    pipettes["left"].aspirate(20.0, deck["4"]["A6"])

    pipettes["left"].well_bottom_clearance.dispense = 1.0

    pipettes["left"].dispense(20.0, deck["1"]["A6"])

    pipettes["left"].blow_out()

    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[6])

    pipettes["left"].well_bottom_clearance.aspirate = 1.0

    pipettes["left"].aspirate(20.0, deck["4"]["A7"])

    pipettes["left"].well_bottom_clearance.dispense = 1.0

    pipettes["left"].dispense(20.0, deck["1"]["A7"])

    pipettes["left"].blow_out()

    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["10"].wells()[7])

    pipettes["left"].well_bottom_clearance.aspirate = 1.0

    pipettes["left"].aspirate(20.0, deck["4"]["A8"])

    pipettes["left"].well_bottom_clearance.dispense = 1.0

    pipettes["left"].dispense(20.0, deck["1"]["A8"])

    pipettes["left"].blow_out()

    pipettes["left"].drop_tip()
