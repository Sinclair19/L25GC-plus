#!/bin/bash
set -e

# ==============================================================================
# Script: update_xio.sh
# Purpose: Update vendored X-IO packages in Go module cache with local code
# ==============================================================================

# ------------------------------------------------------------------------------
# Constants and Formatting
# ------------------------------------------------------------------------------

YELLOW='\033[1;33m'
NC='\033[0m'

WORKDIR=$(pwd)
GOMODCACHE="${GOMODCACHE:-$HOME/go/pkg/mod}"
GOMOD_DIR="$GOMODCACHE/github.com/nycu-ucr"

# ------------------------------------------------------------------------------
# Check if target directory exists
# ------------------------------------------------------------------------------

if [ ! -d "$GOMOD_DIR" ]; then
  echo -e "${YELLOW}[WARN] Go module directory not found at $GOMOD_DIR.${NC}"
  echo -e "       Ensure Go modules have been downloaded before running this script."
  exit 1
fi

echo -e "[INFO] Scanning vendored modules under ${YELLOW}$GOMOD_DIR${NC}..."

# ------------------------------------------------------------------------------
# X-IO Replacement Loop
# ------------------------------------------------------------------------------
cd $GOMOD_DIR
targets=$(find . -maxdepth 1 -type d -name 'onvmpoller@*' -printf '%f\n')
if [ -z "$targets" ]; then
    echo -e "${YELLOW}[WARN] No onvmpoller module found under $GOMOD_DIR.${NC}"
    echo -e "       Run 'go mod download github.com/nycu-ucr/onvmpoller' before update_xio.sh."
    exit 1
fi

for target in $targets; do
    echo -e "[INFO] Processing module: ${YELLOW}${target}${NC}"
    cd "$GOMOD_DIR"

    # Copy updated source files
    chmod -R u+w "$target" || true
    cp -R "$WORKDIR/NFs/xio/." "$target"

    # Perform path replacements
    cd "$target"
    echo -e "[INFO] Replacing hardcoded paths with ${YELLOW}$HOME${NC}"
    sed -i "s#/home/hstsai#$HOME#g" poller.go
    sed -i "s#/home/hstsai#$HOME#g" onvm_poller.c
    sed -i "s#/home/johnson#$HOME#g" poller.go
    sed -i "s#/home/johnson#$HOME#g" onvm_poller.c

    # Remove potentially problematic Go file
    rm -f listen.go
done
