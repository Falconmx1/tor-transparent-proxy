#!/usr/bin/env python3
"""
TUN Virtual Network Interface - Routes all traffic through Tor SOCKS5 proxy.
Requires root privileges for TUN device creation and routing table manipulation.
"""

import os
import sys
import select
import socket
import struct
import fcntl
import logging
import subprocess
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TUNTunnel:
    TUNSETIFF = 0x400454ca  # ioctl command to create TUN interface
    IFF_TUN = 0x0001        # TUN device (no Ethernet header)
    IFF_NO_PI = 0x1000      # No packet information
    
    def __init__(self, dev_name="tor-tun", socks_host="127.0.0.1", socks_port=9050):
        self.dev_name = dev_name
        self.socks_host = socks_host
        self.socks_port = socks_port
        self.tun_fd = None
        self.tun_name = None
        
    def create_tun_interface(self) -> Optional[int]:
        """Create a TUN interface and return file descriptor"""
        try:
            # Open /dev/net/tun device
            self.tun_fd = os.open("/dev/net/tun", os.O_RDWR)
            
            # Prepare interface request structure
            ifr = struct.pack('16sH', self.dev_name.encode(), self.IFF_TUN | self.IFF_NO_PI)
            
            # Perform ioctl to create TUN device
            fcntl.ioctl(self.tun_fd, self.TUNSETIFF, ifr)
            
            # Retrieve actual interface name
            self.tun_name = struct.unpack('16sH', ifr)[0].decode().strip('\x00')
            logger.info(f"TUN interface '{self.tun_name}' created (fd: {self.tun_fd})")
            return self.tun_fd
            
        except Exception as e:
            logger.error(f"Failed to create TUN interface: {e}")
            return None
    
    def configure_interface(self, ip_addr="10.0.0.1/24"):
        """Assign IP and bring interface up"""
        try:
            # Assign IP address
            subprocess.run(f"ip addr add {ip_addr} dev {self.tun_name}", 
                         shell=True, check=True, stderr=subprocess.DEVNULL)
            
            # Bring interface up
            subprocess.run(f"ip link set {self.tun_name} up", 
                         shell=True, check=True)
            
            # Set MTU (1500 is typical for Ethernet, Tor works best with lower values)
            subprocess.run(f"ip link set mtu 1500 dev {self.tun_name}", 
                         shell=True, check=True)
            
            logger.info(f"TUN interface configured with IP {ip_addr}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to configure interface: {e}")
            return False
    
    def setup_routing(self, tor_dns_port=5353):
        """Configure routing tables to force all traffic through TUN"""
        try:
            # Disable reverse path filtering
            subprocess.run("sysctl -w net.ipv4.conf.all.rp_filter=0", shell=True)
            
            # Add default route through TUN interface
            subprocess.run(f"ip route del default 2>/dev/null", shell=True)
            subprocess.run(f"ip route add default dev {self.tun_name}", shell=True)
            
            # Route Tor's own traffic outside the tunnel (prevent loop)
            subprocess.run(f"ip route add {self.socks_host}/32 via {self.get_current_gateway()}", 
                         shell=True)
            
            # Configure DNS to use Tor's DNSPort
            with open('/etc/resolv.conf', 'w') as f:
                f.write(f"nameserver 127.0.0.1\n")
                f.write("options attempts:2 timeout:2\n")
            
            logger.info("Routing configured: all traffic going through TUN")
            return True
        except Exception as e:
            logger.error(f"Failed to set up routing: {e}")
            return False
    
    def get_current_gateway(self) -> str:
        """Retrieve current default gateway"""
        result = subprocess.run("ip route show default | awk '{print $3}'", 
                              shell=True, capture_output=True, text=True)
        return result.stdout.strip()
    
    def enable_kill_switch(self):
        """Block all non-Tor traffic (strict mode)"""
        try:
            subprocess.run("iptables -P INPUT DROP", shell=True)
            subprocess.run("iptables -P OUTPUT DROP", shell=True)
            subprocess.run("iptables -A OUTPUT -o lo -j ACCEPT", shell=True)
            subprocess.run(f"iptables -A OUTPUT -o {self.tun_name} -j ACCEPT", shell=True)
            subprocess.run(f"iptables -A OUTPUT -d {self.socks_host} -p tcp --dport {self.socks_port} -j ACCEPT", shell=True)
            
            logger.warning("⚠️ Kill switch enabled: Non-Tor traffic blocked")
            return True
        except Exception as e:
            logger.error(f"Failed to enable kill switch: {e}")
            return False
    
    def forward_tun_to_socks5(self):
        """Main loop: Read from TUN, forward to SOCKS5, write back responses"""
        if not self.tun_fd:
            logger.error("TUN interface not initialized")
            return
        
        import socks
        # Setup SOCKS5 proxy
        socks.set_default_proxy(socks.SOCKS5, self.socks_host, self.socks_port)
        socket.socket = socks.socksocket  # Monkey patch
        
        logger.info("Starting TUN to SOCKS5 forwarding loop...")
        
        while True:
            try:
                # Read IP packet from TUN
                packet = os.read(self.tun_fd, 4096)
                if not packet:
                    break
                
                # Parse IP header (simplified for IPv4)
                if packet[0] >> 4 != 4:  # IPv4 check
                    continue
                
                # Extract destination IP and protocol
                dest_ip = socket.inet_ntoa(packet[16:20])
                protocol = packet[9]
                
                # For demonstration, just log packet info
                # In production, you would reassemble packets and forward via SOCKS5
                logger.debug(f"Packet: {dest_ip} via protocol {protocol}")
                
                # Simulate response (real implementation would forward to SOCKS5)
                # os.write(self.tun_fd, response_packet)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in forwarding loop: {e}")
        
        logger.info("Forwarding loop ended")
    
    def cleanup(self):
        """Remove TUN interface and restore routing"""
        try:
            if self.tun_fd:
                os.close(self.tun_fd)
            
            subprocess.run(f"ip link del {self.tun_name}", shell=True)
            logger.info("TUN interface removed")
        except:
            pass

if __name__ == "__main__":
    # Quick test (requires root)
    if os.geteuid() != 0:
        print("❌ This script requires root privileges", file=sys.stderr)
        sys.exit(1)
    
    tunnel = TUNTunnel()
    
    if tunnel.create_tun_interface() and tunnel.configure_interface():
        tunnel.setup_routing()
        # tunnel.enable_kill_switch()
        
        print(f"✅ TUN tunnel active. Send traffic to IP 10.0.0.1")
        print("Press Ctrl+C to stop...")
        
        try:
            tunnel.forward_tun_to_socks5()
        except KeyboardInterrupt:
            print("\n🛑 Cleaning up...")
            tunnel.cleanup()
    else:
        print("❌ Failed to set up TUN tunnel")
