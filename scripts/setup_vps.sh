#!/bin/bash
# === TradingSystem Elite Colocation Setup (NJ/NY/LDN) ===
# Target OS: Ubuntu 22.04 LTS
# Purpose: Low-latency optimization and institutional-grade hardening.

set -e
echo "Starting Institutional VPS Hardening..."

# 1. Update and Install Core Dependencies
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3.11 python3.11-venv python3-pip git build-essential \
    libpq-dev libuv1-dev docker.io docker-compose ufw curl

# 2. Network Tuning (Low-Latency TCP)
echo "Optimizing Network Stack for HFT..."
cat <<EOF | sudo tee -a /etc/sysctl.conf
# Increase max open files
fs.file-max = 1000000
# TCP Fast Open
net.ipv4.tcp_fastopen = 3
# Low Latency Socket Tuning
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
# Disable TCP slow start after idling
net.ipv4.tcp_slow_start_after_idle = 0
EOF
sudo sysctl -p

# 3. QuestDB Installation (Docker)
echo "Deploying QuestDB (Time-Series Database)..."
docker run -d \
  --name questdb \
  -p 9000:9000 -p 9009:9009 -p 8812:8812 -p 9003:9003 \
  questdb/questdb:latest

# 4. Security Hardening (Firewall)
echo "Configuring Firewall..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 8080/tcp # Cockpit (if used)
sudo ufw --force enable

# 5. Application Setup
echo "Creating Application Directory..."
mkdir -p ~/TradingSystem
# Instructions: Copy project files here, create venv, and run.

echo "=== VPS SETUP COMPLETE ==="
echo "Next Steps:"
echo "1. SCP your code to ~/TradingSystem"
echo "2. Run: python3.11 -m venv venv"
echo "3. Run: source venv/bin/activate && pip install -r requirements.txt"
echo "4. Activate QuestDB in .env (QUESTDB_ENABLED=True)"
