# Tor Transparent Proxy (VPN-over-Tor)

⚠️ **EDUCATIONAL PURPOSE ONLY** - This tool demonstrates network tunneling concepts.
Use responsibly and in compliance with local laws.

## 🔒 Threat Model
- **Provides**: Anonymous browsing via Tor network
- **Does NOT provide**: End-to-end encryption, protection from malicious exit nodes
- **Limitations**: No protection against browser fingerprints, timing attacks

## 📋 Features
- Transparent proxy via Linux network namespaces
- DNS leak protection (forwards through Tor)
- Kill switch (blocks non-Tor traffic)
- Docker/container support

## 🚀 Quick Start
```bash
git clone https://github.com/Falconmx1/tor-transparent-proxy
cd tor-transparent-proxy
sudo ./setup.sh

⚠️ Legal Notice

This software is for educational purposes only. Users are responsible for compliance with local laws.
🤝 Contributing

See CONTRIBUTING.md
📚 Resources

    Tor Project Documentation

    Linux Network Namespaces
