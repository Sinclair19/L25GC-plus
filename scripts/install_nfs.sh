#!/bin/bash -i
set -e

# ==============================================================================
# L25GC+ Control Plane and User Plane Setup Script
# ==============================================================================

# ------------------------------------------------------------------------------
# Color Constants for Logging
# ------------------------------------------------------------------------------

BLUE='\033[1;34m'
YELLOW='\033[1;33m'
GREEN='\033[1;32m'
RED='\033[1;31m'
NC='\033[0m' # No Color

WORK_DIR="$HOME/L25GC-plus"
ONVM_HOME="$WORK_DIR/NFs/onvm-upf"

# ------------------------------------------------------------------------------
# Update and Install Basic Packages
# ------------------------------------------------------------------------------

cd $HOME
sudo NEEDRESTART_MODE=a apt -y install cmake autoconf libtool pkg-config libmnl-dev

# ------------------------------------------------------------------------------
# Clone and Initialize Control Plane NFs
# ------------------------------------------------------------------------------

echo "[INFO] Cloning L25GC+ and dependencies..."
cd "$WORK_DIR"
git submodule sync
git submodule update --init

# ------------------------------------------------------------------------------
# Clone and Build ONVM
# ------------------------------------------------------------------------------

cd "$ONVM_HOME"

git submodule sync
git submodule update --init

echo -e "${YELLOW}Build and install DPDK, go1.21, igb_uio${NC}"
./scripts/install.sh
./scripts/setup_runtime.sh

# Source .bashrc to make Go env active
source ~/.bashrc

# Building ONVM, UPF-U, and UPF-C
./scripts/build.sh

# ------------------------------------------------------------------------------
# Setup Environment Variables
# ------------------------------------------------------------------------------

cd "$WORK_DIR"
sudo rm -rf $HOME/.cache

echo "export ONVMPOLLER_IPID_YAML=$HOME/L25GC-plus/onvm_nf_configs/ipid.yaml" >> ~/.bashrc
echo "export ONVMPOLLER_NFIP_YAML=$HOME/L25GC-plus/onvm_nf_configs/NFip.yaml" >> ~/.bashrc
echo "export ONVMPOLLER_IPID_TXT=$HOME/L25GC-plus/onvm_nf_configs/ipid.txt" >> ~/.bashrc
echo "export CGO_LDFLAGS_ALLOW='-Wl,(--whole-archive|--no-whole-archive)'" >> ~/.bashrc
echo "export ONVM_NF_JSON=$HOME/L25GC-plus/onvm_nf_configs/" >> ~/.bashrc

export ONVMPOLLER_IPID_YAML="$WORK_DIR/onvm_nf_configs/ipid.yaml"
export ONVMPOLLER_NFIP_YAML="$WORK_DIR/onvm_nf_configs/NFip.yaml"
export ONVMPOLLER_IPID_TXT="$WORK_DIR/onvm_nf_configs/ipid.txt"
export ONVM_NF_JSON="$WORK_DIR/onvm_nf_configs/"
export CGO_LDFLAGS_ALLOW='-Wl,(--whole-archive|--no-whole-archive)'

export CGO_CFLAGS="${CGO_CFLAGS:-} -I$ONVM_HOME/onvm/onvm_nflib -I$ONVM_HOME/onvm/lib -I/usr/local/include"

# ------------------------------------------------------------------------------
# Build Control Plane NFs and Link X-IO
# ------------------------------------------------------------------------------

echo "[INFO] Pre-downloading onvmpoller so update_xio can patch the module cache..."
cd "$WORK_DIR/NFs/nrf"
go mod download github.com/nycu-ucr/onvmpoller

cd "$WORK_DIR"
./scripts/update_xio.sh

# 5GC NFs to Compile
NFs="nrf amf smf udr pcf udm nssf ausf chf"
for nf in $NFs
do
    ./scripts/update_xio.sh
    rm -rf $HOME/.cache
    make $nf
done
# done

# ------------------------------------------------------------------------------
# Final Onvmpoller Update and Cleanup
# ------------------------------------------------------------------------------

cd "$WORK_DIR"
./scripts/update_xio.sh
sudo rm -rf ~/.cache

# Optional cleanup (commented out)
# cd $HOME/L25GC-plus/onvm_test
# sudo rm -rf ~/go/pkg/mod/github.com
# sudo rm -rf ~/go/pkg/mod/cache
# go mod tidy

source ~/.bashrc

echo -e "${GREEN}Setup complete!${NC}"
