# TODO: this is not ready to actually be considered a test yet...
"""test ot2 streaming"""
from argparse import ArgumentParser
from pathlib import Path

from ot2_driver.ot2_driver_http import OT2_Config, OT2_Driver


# cant name it test because it does not actually test anything right now...
def streaming_t(ot2: OT2_Driver):
    """test ot2 streaming"""
    run_id = ot2.stream(
        command="loadLabware",
        params={
            "location": {"slotName": "1"},
            "loadName": "corning_96_wellplate_360ul_flat",
            "namespace": "opentrons",
            "version": "1",
            "labwareId": "wellplate_1",
        },
        execute=False,
        intent="setup",
    )
    print()
    print()

    ot2.stream(
        command="loadLabware",
        params={
            "location": {"slotName": "2"},
            "loadName": "opentrons_96_tiprack_300ul",
            "namespace": "opentrons",
            "version": "1",
            # "labwareId": "tiprack_1",
        },
        run_id=run_id,
        execute=False,
        intent="setup",
    )
    print()
    print()

    ot2.stream(
        command="loadPipette",
        params={
            "pipetteName": "p300_multi_gen2",
            "mount": "right",
            "pipetteId": "p300_right",
        },
        run_id=run_id,
        execute=False,
        intent="setup",
    )
    print()
    print()

    ot2.stream(
        command="moveRelative",
        params={"pipetteId": "p300_right", "axis": "x", "distance": "-100"},
        run_id=run_id,
        execute=False,
    )
    ot2.stream(
        command="moveRelative",
        params={"pipetteId": "p300_right", "axis": "x", "distance": "-200"},
        run_id=run_id,
        execute=True,
    )

    exit()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-c", "--config", help="Path to robot config file", type=Path)

    args = parser.parse_args()

    config = OT2_Config.from_yaml(args.config)
