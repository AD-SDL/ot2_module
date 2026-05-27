FROM ghcr.io/ad-sdl/madsci:v0.8.0

LABEL org.opencontainers.image.source=https://github.com/AD-SDL/ot2_module
LABEL org.opencontainers.image.description="Drivers and REST API's for the Opentrons OT2 LiquidHandling robots"
LABEL org.opencontainers.image.licenses=MIT

#########################################
# Module specific logic goes below here #
#########################################

RUN mkdir -p ot2_module

COPY ./src ot2_module/src
COPY ./README.md ot2_module/README.md
COPY ./pyproject.toml ot2_module/pyproject.toml

# Install into the madsci venv (system pip would land in /usr/lib site-packages,
# invisible to the venv interpreter the entrypoint actually runs).
RUN --mount=type=cache,target=/root/.cache \
    uv pip install --python ${MADSCI_VENV}/bin/python -e ./ot2_module

# Note: do not switch USER here — the base entrypoint runs userdel/useradd as
# root to remap UID/GID to the host's, then drops to the madsci user itself.

CMD ["python", "ot2_module/src/ot2_rest_node.py"]

#########################################
