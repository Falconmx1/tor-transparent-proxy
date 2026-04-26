#!/bin/bash
# start.sh - Launches VPN-over-Tor with network namespace isolation

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Tor Transparent Proxy Launcher ===${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (sudo)$NC"
    exit 1
fi

# Configuration
NAMESPACE="tor-ns"
TUN_DEV="tor-tun"
TOR_SOCKS_PORT=9050
TOR_CONTROL_PORT=9051
DNS_PORT=5353

# Kill existing instances
pkill -f "tor" 2>/dev/null || true
ip netns del $NAMESPACE 2>/dev/null || true

echo -e "${YELLOW}[1/6] Creating network namespace...${NC}"
ip netns add $NAMESPACE

echo -e "${YELLOW}[2/6] Creating veth pair for namespace communication...${NC}"
ip link add veth0 type veth peer name veth1
ip link set veth1 netns $NAMESPACE

echo -e "${YELLOW}[3/6] Configuring interfaces...${NC}"
ip addr add 10.0.0.1/24 dev veth0
ip link set veth0 up
ip netns exec $NAMESPACE ip addr add 10.0.0.2/24 dev veth1
ip netns exec $NAMESPACE ip link set veth1 up
ip netns exec $NAMESPACE ip link set lo up

# Default route inside namespace
ip netns exec $NAMESPACE ip route add default via 10.0.0.1

echo -e "${YELLOW}[4/6] Enabling IP forwarding and NAT...${NC}"
sysctl -w net.ipv4.ip_forward=1 > /dev/null
iptables -t nat -A POSTROUTING -s 10.0.0.0/24 -o eth0 -j MASQUERADE
iptables -A FORWARD -i veth0 -o eth0 -j ACCEPT
iptables -A FORWARD -i eth0 -o veth0 -j ACCEPT

echo -e "${YELLOW}[5/6] Starting Tor inside namespace...${NC}"
# Copy Tor configuration to namespace
mkdir -p /etc/tor
cp config/torrc /etc/tor/torrc

# Launch Tor in the namespace
ip netns exec $NAMESPACE tor -f /etc/tor/torrc --RunAsDaemon 1
sleep 3  # Wait for Tor to boot

echo -e "${YELLOW}[6/6] Testing connection...${NC}"
# Test Tor connectivity from namespace
if ip netns exec $NAMESPACE curl --socks5-hostname 127.0.0.1:$TOR_SOCKS_PORT -s https://check.torproject.org/api/ip | grep -q '"IsTor":true'; then
    echo -e "${GREEN}✅ Tor is working inside the namespace!${NC}"
else
    echo -e "${RED}❌ Tor test failed${NC}"
    exit 1
fi

# Setup namespace routing to force everything through Tor
cat > /tmp/namespace_setup.sh << EOF
#!/bin/bash
# Route all traffic through Tor
iptables -t nat -A OUTPUT -p tcp --dport 1:65535 ! -d 127.0.0.1 -j REDIRECT --to-ports $TOR_SOCKS_PORT
iptables -t nat -A OUTPUT -p udp --dport 53 -j REDIRECT --to-ports $DNS_PORT
EOF

chmod +x /tmp/namespace_setup.sh
ip netns exec $NAMESPACE /tmp/namespace_setup.sh

echo -e "${GREEN}=== Setup Complete ==="
echo -e "To run a command inside the Tor-routed namespace:"
echo -e "  ${YELLOW}sudo ip netns exec $NAMESPACE <command>${NC}"
echo -e "Example:"
echo -e "  ${YELLOW}sudo ip netns exec $NAMESPACE curl --socks5-hostname 127.0.0.1:$TOR_SOCKS_PORT https://check.torproject.org${NC}"
echo -e ""
echo -e "To clean up:"
echo -e "  ${YELLOW}sudo ./scripts/stop.sh${NC}"

# Optional: Launch a shell in the namespace
read -p "Launch a bash shell inside the Tor namespace? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}Entering Tor-routed namespace. Type 'exit' to return.${NC}"
    ip netns exec $NAMESPACE bash --rcfile <(echo "PS1='tor-ns:\w\$ '")
fi
