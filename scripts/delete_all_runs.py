import requests
from argparse import ArgumentParser


def main(args):
    base_url = "http://{ip_address}:31950/{extension}"
    headers = {"Opentrons-Version": "2"}

    # get all runs
    runs_resp = requests.get(
        url=base_url.format(ip_address=args.ip_address, extension="runs"),
        headers=headers,
    )

    if runs_resp.status_code != 200:
        raise Exception(
            f"Request not completed with status code {runs_resp.status_code} and error: {runs_resp.json()}"
        )

    for run in runs_resp.json()["data"]:
        run_id = run["id"]

        delete_resp = requests.delete(
            url=base_url.format(ip_address=args.ip_address, extension=f"runs/{run_id}"),
            headers=headers,
        )
        if delete_resp.status_code != 200:
            print(f"Could not delete run with ID {run_id}, response: {delete_resp.json()}")
        else:
            print(f"Run {run_id} deleted...")

    print(f"All runs deleted on OT2:{args.ip_address}")


if __name__ == "__main__":
    parser = ArgumentParser(description="Delete all runs stored on an ot2 with a given ip address")
    parser.add_argument("-ip", "--ip_address", help="Robot IP to delete all runs from", type=str)

    args = parser.parse_args()
    main(args)
