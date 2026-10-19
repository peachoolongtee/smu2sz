#!/usr/bin/env bash
# One-time preparation of an Ubuntu 24.04 VM for the judges' demo: Docker, a swap file for the web build, unattended
# security updates, and a firewall that admits only SSH, HTTP and HTTPS. Run as the admin user (uses sudo).
set -euo pipefail
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q docker.io docker-compose-v2 unattended-upgrades ufw
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab >/dev/null
fi
sudo ufw allow 22/tcp >/dev/null && sudo ufw allow 80/tcp >/dev/null && sudo ufw allow 443/tcp >/dev/null
sudo ufw --force enable >/dev/null
echo "server ready: $(docker --version); $(docker compose version)"
