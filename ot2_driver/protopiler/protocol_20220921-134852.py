from opentrons import protocol_api


metadata = {
    "protocolName": "Example Name",
    "author": "Kyle khippe@anl.gov",
    "description": "dimension_all.yml",
    "apiLevel": "2.12"
}

def run(protocol: protocol_api.ProtocolContext):

    deck = {}
    pipettes = {}

    ################
    # load labware #
    ################
    deck["1"] = protocol.load_labware("corning_96_wellplate_360ul_flat", "1")
    deck["8"] = protocol.load_labware("opentrons_96_tiprack_20ul", "8")
    deck["9"] = protocol.load_labware("opentrons_96_tiprack_1000ul", "9")
    pipettes["right"] = protocol.load_instrument("p20_single_gen2", "right", tip_racks=[deck["8"]])
    pipettes["left"] = protocol.load_instrument("p1000_single_gen2", "left", tip_racks=[deck["9"]])

    ####################
    # execute commands #
    ####################

    # example command
    pipettes["right"].pick_up_tip(deck["8"].wells()[0])
    pipettes["right"].aspirate(15, deck["1"]["A1"])
    pipettes["right"].dispense(15, deck["1"]["B1"])
    pipettes["right"].drop_tip()

    pipettes["left"].pick_up_tip(deck["9"].wells()[0])
    pipettes["left"].aspirate(100, deck["1"]["A2"])
    pipettes["left"].dispense(100, deck["1"]["B2"])
    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["9"].wells()[1])
    pipettes["left"].aspirate(700, deck["1"]["A3"])
    pipettes["left"].dispense(700, deck["1"]["B3"])
    pipettes["left"].drop_tip()
