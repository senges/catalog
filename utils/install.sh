#!/bin/sh
# -*- coding: utf-8 -*-
# =============================================================================
# Author : @senges
# Version : April 2022
# Description : Install catalog
#
# Run (either with wget or curl):
#  sh -c "$(wget -qO- https://raw.githubusercontent.com/senges/catalog/main/utils/install.sh)"
#  sh -c "$(curl -fsSL https://raw.githubusercontent.com/senges/catalog/main/utils/install.sh)"
# =============================================================================

INSTALL_DIR=/opt/catalog

# Setup catalog requirements
apt update
apt install -y python3

# Install catalog
# (Note: do not clone if called from Dockerfile) 
if [ ! -d "$INSTALL_DIR" ]; then
    apt install -y git
    git clone --depth 1 https://github.com/senges/catalog.git /opt/catalog
fi

python3 /opt/catalog/catalog.py --init

# Cleanup
rm -rf /var/lib/apt/lists/*