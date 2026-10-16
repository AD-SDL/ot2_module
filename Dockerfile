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

# Extras to install alongside the module. Empty for a production image; set to
# "[simulation]" to pull in Opentrons' simulator, which simulation mode uses to
# execute a compiled protocol without a robot. It adds roughly 54 MB, so the
# default build does not carry it.
#   docker build --build-arg MODULE_EXTRAS="[simulation]" -t ot2_module:sim .
ARG MODULE_EXTRAS=""

# Install into the madsci venv (system pip would land in /usr/lib site-packages,
# invisible to the venv interpreter the entrypoint actually runs).
RUN --mount=type=cache,target=/root/.cache \
    uv pip install --python ${MADSCI_VENV}/bin/python -e "./ot2_module${MODULE_EXTRAS}"

# Note: do not switch USER here — the base entrypoint runs userdel/useradd as
# root to remap UID/GID to the host's, then drops to the madsci user itself.

CMD ["python", "ot2_module/src/ot2_rest_node.py"]

#########################################
