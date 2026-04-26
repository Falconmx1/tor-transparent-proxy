#!/usr/bin/env python3
"""
Tor Controller with SOCKS5 proxy management using Stem.
Handles Tor process lifecycle, configuration, and circuit management.
"""

import os
import sys
import time
import logging
from stem import Signal
from stem.control import Controller
from stem.process import launch_tor_with_config
import subprocess

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TorProxy:
    def __init__(self, torrc_path=None, data_dir='/tmp/tor_data', socks_port=9050, control_port=9051):
        self.torrc_path = torrc_path or '/etc/tor/torrc'
        self.data_dir = data_dir
        self.socks_port = socks_port
        self.control_port = control_port
        self.tor_process = None
        self.controller = None
        
    def configure_torrc(self):
        """Generate or update torrc with secure defaults"""
        config = {
            'SOCKSPort': f'127.0.0.1:{self.socks_port}',
            'ControlPort': str(self.control_port),
            'DataDirectory': self.data_dir,
            'CookieAuthentication': '1',
            'SafeLogging': '1',
            'ExitRelay': '0',
            'ClientOnly': '1',
            'NewCircuitPeriod': '40',
            'MaxCircuitDirtiness': '60',
            'LearnCircuitBuildTimeout': '1',
            'CircuitBuildTimeout': '30',
            'KeepalivePeriod': '300',
            'NumEntryGuards': '4',
            'UseEntryGuards': '1',
            'DNSListenAddress': '0.0.0.0',
            'DNSPort': '5353',
            'AutomapHostsOnResolve': '1',
            'VirtualAddrNetworkIPv4': '10.192.0.0/10',
        }
        
        with open(self.torrc_path, 'w') as f:
            for key, value in config.items():
                f.write(f'{key} {value}\n')
        logger.info(f"Tor configuration written to {self.torrc_path}")
        
    def start_tor(self):
        """Launch Tor daemon with custom configuration"""
        self.configure_torrc()
        
        try:
            self.tor_process = launch_tor_with_config(
                config={
                    'SOCKSPort': f'127.0.0.1:{self.socks_port}',
                    'ControlPort': str(self.control_port),
                    'DataDirectory': self.data_dir,
                    'CookieAuthentication': '1',
                },
                tor_cmd='tor',
                completion_percent=100,
                timeout=90,
                take_ownership=True,
            )
            logger.info(f"Tor started successfully on SOCKS5 port {self.socks_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start Tor: {e}")
            return False
    
    def connect_controller(self):
        """Connect to Tor's control port for dynamic management"""
        try:
            self.controller = Controller.from_port(port=self.control_port)
            self.controller.authenticate()
            logger.info("Connected to Tor controller")
            return True
        except Exception as e:
            logger.error(f"Could not connect to Tor controller: {e}")
            return False
    
    def renew_circuit(self):
        """Request a new Tor circuit (new identity)"""
        if not self.controller:
            logger.error("No controller connection")
            return False
        
        try:
            self.controller.signal(Signal.NEWNYM)
            logger.info("New Tor circuit requested")
            return True
        except Exception as e:
            logger.error(f"Failed to renew circuit: {e}")
            return False
    
    def get_circuit_status(self):
        """Return current circuit information"""
        if not self.controller:
            return None
        
        circuits = []
        for circ in self.controller.get_circuits():
            circuits.append({
                'id': circ.id,
                'status': circ.status,
                'purpose': circ.purpose,
                'path': [f"{fp[0]}~{fp[1]}" for fp in circ.path],
                'build_flags': circ.build_flags
            })
        return circuits
    
    def stop_tor(self):
        """Clean shutdown of Tor process"""
        if self.controller:
            self.controller.close()
        
        if self.tor_process:
            self.tor_process.terminate()
            self.tor_process.wait()
            logger.info("Tor stopped")
    
    def verify_proxy(self):
        """Test SOCKS5 proxy functionality"""
        import socks
        import socket
        
        try:
            s = socks.socksocket()
            s.set_proxy(socks.SOCKS5, "127.0.0.1", self.socks_port)
            s.settimeout(10)
            s.connect(("check.torproject.org", 80))
            s.send(b"GET / HTTP/1.0\r\nHost: check.torproject.org\r\n\r\n")
            response = s.recv(1024).decode()
            s.close()
            
            if "Congratulations" in response:
                logger.info("✅ Tor proxy is working correctly")
                return True
            else:
                logger.warning("⚠️ Proxy test ambiguous")
                return False
        except Exception as e:
            logger.error(f"❌ Proxy test failed: {e}")
            return False

if __name__ == "__main__":
    # Test the Tor controller
    tor = TorProxy()
    
    if tor.start_tor():
        time.sleep(2)  # Wait for Tor to stabilize
        tor.connect_controller()
        
        if tor.verify_proxy():
            print("=== Circuit Status ===")
            circuits = tor.get_circuit_status()
            for circ in circuits:
                print(f"Circuit {circ['id']}: {circ['status']} - Path: {' -> '.join(circ['path'])}")
            
            print("\n🔄 Renewing circuit...")
            tor.renew_circuit()
            time.sleep(5)
            print("Circuit renewed!")
        
        tor.stop_tor()
    else:
        sys.exit(1)
