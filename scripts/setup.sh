#!/bin/bash
# setup.sh - Installs dependencies for tor-transparent-proxy

set -e

echo "[*] Installing system dependencies..."
sudo apt update
sudo apt install -y tor python3 python3-pip iptables \
    net-tools iproute2 dnsmasq

echo "[*] Installing Python packages..."
pip3 install stem[pt]  # Tor controller library
pip3 install dnspython netifaces

echo "[*] Creating config directories..."
sudo mkdir -p /etc/tor-transparent-proxy
sudo cp config/torrc /etc/tor-transparent-proxy/

echo "[✓] Setup complete. Run 'sudo ./scripts/start.sh' to launch"
