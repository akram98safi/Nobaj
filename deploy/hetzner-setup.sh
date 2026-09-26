#!/usr/bin/env bash
# ==============================================================================
# Nobaj Platform - Automated Hetzner Server Setup Script
# Works on Ubuntu 22.04 LTS / 24.04 LTS
# ==============================================================================

set -e

echo "=========================================================="
echo "    🚀 Nobaj Media Tools - Hetzner Server Provisioning   "
echo "=========================================================="

# Check root privileges
if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root (use: sudo bash hetzner-setup.sh)"
  exit 1
fi

echo "📦 Step 1: Updating system packages..."
apt-get update && apt-get upgrade -y
apt-get install -y curl git ufw ca-certificates gnupg lsb-release

echo "🐳 Step 2: Installing Docker and Docker Compose..."
if ! command -v docker &> /dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    echo "✅ Docker installed successfully."
else
    echo "✅ Docker is already installed."
fi

echo "🛡️ Step 3: Configuring Firewall (UFW)..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw --force enable

echo "⚙️ Step 4: Configuring Environment File..."
if [ ! -f .env ]; then
    cp .env.example .env
    ADMIN_TOKEN=$(openssl rand -hex 32)
    sed -i "s/^ADMIN_TOKEN=$/ADMIN_TOKEN=${ADMIN_TOKEN}/" .env
    echo "✅ Created .env with freshly generated SECRET_KEY and ADMIN_TOKEN."
elif ! grep -q "^ADMIN_TOKEN=.\+" .env; then
    ADMIN_TOKEN=$(openssl rand -hex 32)
    printf "\nADMIN_TOKEN=%s\n" "${ADMIN_TOKEN}" >> .env
    echo "✅ Added a freshly generated ADMIN_TOKEN to the existing .env."
fi

echo "🚀 Step 5: Building and Starting Nobaj with Docker Compose..."
docker compose --profile production up -d --build

echo "=========================================================="
echo "    🎉 Nobaj has been successfully deployed!             "
echo "=========================================================="
echo "Access your instance at: http://$(curl -fsS --max-time 5 https://api.ipify.org || echo '<SERVER_IP>')"
echo "Check container status: docker compose ps"
echo "View live logs:         docker compose logs -f"
echo "=========================================================="
