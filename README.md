# ot2_module

A MADSci node module for integrating opentrons liquid handlers (both OT-2 and Flex, despite the name) into an automated/autonomous laboratory.

You can find example definition and info files in the `definitions` folder.

## Installation and Usage

### Python

```bash
# Create a virtual environment named .venv
python -m venv .venv
# Activate the virtual environment on Linux or macOS
source .venv/bin/activate
# Alternatively, activate the virtual environment on Windows
# .venv\Scripts\activate
# Install the module and dependencies in the venv
pip install .
# Start the node
python -m ot2_rest_node --node_definition <path/to/definition> --node_url http://localhost:2000
```

### Docker

- We provide a `Dockerfile` and example docker compose file (`compose.yaml`) to run this node dockerized.
- There is also a pre-built image available as `ghcr.io/ad-sdl/ot2_module`.
- You can control the container user's id and group id by setting the `USER_ID` and `GROUP_ID`

### Getting the OT2 setup for ssh

*This is not required (or used) for the HTTP driver*

When setting up an ssh key to connect to the opentrons, it is helpful to make a new one without a passphrase. For more information on setting up an ssh connection see:

*Note, you have to have the Opentrons App installed*

- https://support.opentrons.com/en/articles/3203681-setting-up-ssh-access-to-your-ot-2
- https://support.opentrons.com/en/articles/3287453-connecting-to-your-ot-2-with-ssh

For prototyping in the RPL, connect via the wire and wait for the robot to become visible on the application. Click `settings` then `network settings` and if you intend on running via the wire, use the `wired-ip` in the robot configuration file. If you intend to use the wireless IP, you must connect to the `snowcrash` network, but this does not have internet access.
