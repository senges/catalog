ARG UBUNTU_VERSION=22.04

FROM ubuntu:${UBUNTU_VERSION} as ubuntu

# Building stage
# FROM ubuntu

ARG DEBIAN_FRONTEND=noninteractive

ENV PATH="${PATH}:/opt/bin"

COPY . /opt/catalog

RUN mkdir -p /opt/bin \
    && apt update \
    && apt install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && ln -fs "$(which python3)" /bin/python \
    && ln -fs "$(which pip3)" /bin/pip \
    && ln -fs /opt/catalog/catalog.py /opt/bin/catalog

RUN catalog --rm-cache -v utils.min npm golang gem 