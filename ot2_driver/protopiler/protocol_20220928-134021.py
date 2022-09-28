from opentrons import protocol_api


metadata = {
    "protocolName": "PCR master mix example",
    "author": "Abe astroka@anl.gov",
    "description": "Mixes master mix for PCR protocol using reagents in 15 well tube rack",
    "apiLevel": "2.12"
}

def run(protocol: protocol_api.ProtocolContext):

    deck = {}
    pipettes = {}

    ################
    # load labware #
    ################
    deck["1"] = protocol.load_labware("opentrons_15_tuberack_nest_15ml_conical", "1")
    deck["8"] = protocol.load_labware("opentrons_96_tiprack_20ul", "8")
    deck["9"] = protocol.load_labware("opentrons_96_tiprack_1000ul", "9")
    pipettes["right"] = protocol.load_instrument("p20_single_gen2", "right", tip_racks=[deck["8"]])
    pipettes["left"] = protocol.load_instrument("p1000_single_gen2", "left", tip_racks=[deck["9"]])

    ####################
    # execute commands #
    ####################

    # DNA Polymerase
    pipettes["right"].pick_up_tip(deck["8"].wells()[0])
    pipettes["right"].aspirate(12, deck["1"]["A1"])
    pipettes["right"].dispense(12, deck["1"]["C3"])
    pipettes["right"].drop_tip()

    pipettes["right"].pick_up_tip(deck["8"].wells()[1])
    pipettes["right"].aspirate(12, deck["1"]["A1"])
    pipettes["right"].dispense(12, deck["1"]["C3"])
    pipettes["right"].drop_tip()


    # 5x Reaction Buffer
    pipettes["left"].pick_up_tip(deck["9"].wells()[0])
    pipettes["left"].aspirate(720, deck["1"]["A2"])
    pipettes["left"].dispense(720, deck["1"]["C3"])
    pipettes["left"].mix(3, 400, deck["1"]["C3"])
    pipettes["left"].drop_tip()


    # Dantes
    pipettes["left"].pick_up_tip(deck["9"].wells()[1])
    pipettes["left"].aspirate(108, deck["1"]["A3"])
    pipettes["left"].dispense(108, deck["1"]["C3"])
    pipettes["left"].mix(3, 500, deck["1"]["C3"])
    pipettes["left"].drop_tip()


    # BioWater
    pipettes["left"].pick_up_tip(deck["9"].wells()[2])
    pipettes["left"].aspirate(676, deck["1"]["A4"])
    pipettes["left"].dispense(676, deck["1"]["C3"])
    pipettes["left"].mix(3, 900, deck["1"]["C3"])
    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["9"].wells()[3])
    pipettes["left"].aspirate(676, deck["1"]["A4"])
    pipettes["left"].dispense(676, deck["1"]["C3"])
    pipettes["left"].mix(3, 900, deck["1"]["C3"])
    pipettes["left"].drop_tip()

    pipettes["left"].pick_up_tip(deck["9"].wells()[4])
    pipettes["left"].aspirate(676, deck["1"]["A4"])
    pipettes["left"].dispense(676, deck["1"]["C3"])
    pipettes["left"].mix(3, 900, deck["1"]["C3"])
    pipettes["left"].drop_tip()


    # GC Enhancer
    pipettes["left"].pick_up_tip(deck["9"].wells()[5])
    pipettes["left"].aspirate(720, deck["1"]["A5"])
    pipettes["left"].dispense(720, deck["1"]["C3"])
    pipettes["left"].mix(7, 900, deck["1"]["C3"])
    pipettes["left"].drop_tip()
