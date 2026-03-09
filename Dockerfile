FROM ghcr.io/ad-sdl/madsci

LABEL org.opencontainers.image.source=https://github.com/AD-SDL/ot2_module
LABEL org.opencontainers.image.description="Drivers and REST API's for the Opentrons OT2 LiquidHandling robots"
LABEL org.opencontainers.image.licenses=MIT

#########################################
# Module specific logic goes below here #
#########################################

ARG USER_ID=9999
ARG GROUP_ID=9999

RUN mkdir -p ot2_module

COPY ./src ot2_module/src
COPY ./README.md ot2_module/README.md
COPY ./pyproject.toml ot2_module/pyproject.toml

RUN --mount=type=cache,target=/root/.cache \
    uv pip install --python ${MADSCI_VENV}/bin/python -e /home/madsci/ot2_module && \
    chown -R ${USER_ID}:${GROUP_ID} /home/madsci/ot2_module

CMD ["python", "-m", "ot2_rest_node"]

#########################################
