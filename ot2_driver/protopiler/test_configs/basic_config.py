from opentrons import protocol_api

metadata = {
    "protocolName": "Example Name",
    "author": "Kyle khippe@anl.gov",
    "description": "basic_config.yml",
    "apiLevel": "2.12",
}


def run(protocol: protocol_api.ProtocolContext):
    deck = {}
    pipettes = {}

    ################
    # load labware #
    ################
    deck["2"] = protocol.load_labware("corning_96_wellplate_360ul_flat", "2")
    deck["3"] = protocol.load_labware("corning_96_wellplate_360ul_flat", "3")
    deck["8"] = protocol.load_labware("opentrons_96_tiprack_1000ul", "8")
    pipettes["right"] = protocol.load_instrument(
        "p1000_single_gen2", "right", tip_racks=[deck["8"]]
    )

    ####################
    # execute commands #
    ####################

    # example command
    pipettes["right"].pick_up_tip(deck["8"].wells()[0])
    pipettes["right"].aspirate(100, deck["2"]["A1"])
    pipettes["right"].dispense(100, deck["3"]["A1"])
    pipettes["right"].drop_tip()

    # other command
    pipettes["right"].pick_up_tip(deck["8"].wells()[1])
    pipettes["right"].aspirate(100, deck["2"]["A2"])
    pipettes["right"].dispense(100, deck["3"]["A2"])
    pipettes["right"].drop_tip()
