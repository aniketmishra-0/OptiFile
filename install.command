#!/bin/bash
# Get the directory of this command script
cd "$(dirname "$0")"

# Ensure execute permissions on install.sh and run it
chmod +x install.sh
./install.sh
