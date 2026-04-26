#!/bin/bash
# stop.sh - Clean up everything

NAMESPACE="tor-ns"
TUN_DEV="tor-tun"

echo "Stopping Tor transparent proxy..."

# Kill Tor processes
pkill -f "tor" 2>/dev/null

# Delete network namespace
ip netns del $NAMESPACE 2>/dev/null

# Remove TUN interface
ip link del $TUN_DEV 2>/dev/null

# Flush iptables rules (careful with this!)
iptables -t nat -F POSTROUTING 2>/dev/null
iptables -F FORWARD 2>/dev/null

# Restore DNS
echo "nameserver 8.8.8.8" > /etc/resolv.conf 2>/dev/null || true

echo "Cleanup complete"
