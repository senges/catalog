# ARG UBUNTU_VERSION=20.04
# FROM ubuntu:${UBUNTU_VERSION} as ubuntu

# Building stage
FROM ubuntu:20.04

ARG DEBIAN_FRONTEND=noninteractive

# Make catalog installed tools available
ENV PATH="${PATH}:/opt/.catalog/bin"

# Install catalog
COPY . /opt/catalog
RUN /bin/bash /opt/catalog/utils/install.sh