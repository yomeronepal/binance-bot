#!/bin/bash

# Initial Server Setup Script for Binance Trading Bot
# Run this script on your server ONCE before first deployment

set -e  # Exit on error

echo "=========================================="
echo "Binance Trading Bot - Server Setup"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root (use: sudo bash server-setup.sh)"
    exit 1
fi

print_info "Starting server setup..."
echo ""

# Step 1: Update system
print_info "Updating system packages..."
apt update && apt upgrade -y
print_status "System updated"
echo ""

# Step 2: Install Docker
print_info "Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    print_status "Docker installed"
else
    print_status "Docker already installed"
fi
echo ""

# Step 3: Install Docker Compose
print_info "Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    apt install docker-compose -y
    print_status "Docker Compose installed"
else
    print_status "Docker Compose already installed"
fi
echo ""

# Step 4: Install required tools
print_info "Installing required tools (rsync, curl, git)..."
apt install -y rsync curl git vim
print_status "Tools installed"
echo ""

# Step 5: Create project directories
print_info "Creating project directories..."
mkdir -p /opt/binance-bot
mkdir -p /opt/binance-bot-backups
chmod 755 /opt/binance-bot
chmod 755 /opt/binance-bot-backups
print_status "Directories created"
echo ""

# Step 6: Configure firewall (optional)
print_info "Configuring firewall..."
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp   # SSH
    ufw allow 80/tcp   # HTTP
    ufw allow 443/tcp  # HTTPS
    ufw --force enable
    print_status "Firewall configured"
else
    print_warning "UFW not installed, skipping firewall configuration"
fi
echo ""

# Step 7: Enable Docker service
print_info "Enabling Docker service..."
systemctl enable docker
systemctl start docker
print_status "Docker service enabled and started"
echo ""

# Step 8: Create a non-root Docker user (optional but recommended)
print_info "Adding current user to Docker group..."
usermod -aG docker $SUDO_USER || true
print_status "User added to Docker group"
echo ""

# Step 9: Test Docker installation
print_info "Testing Docker installation..."
if docker run hello-world &> /dev/null; then
    print_status "Docker is working correctly"
else
    print_error "Docker test failed"
    exit 1
fi
echo ""

# Step 10: Display system information
echo "=========================================="
echo "System Information:"
echo "=========================================="
print_info "Docker version: $(docker --version)"
print_info "Docker Compose version: $(docker-compose --version)"
print_info "Server IP: $(hostname -I | awk '{print $1}')"
print_info "Available disk space: $(df -h /opt | tail -1 | awk '{print $4}')"
print_info "Available memory: $(free -h | grep Mem | awk '{print $7}')"
echo ""

# Step 11: Display next steps
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Generate SSH key for GitHub Actions (if not done):"
echo "   ${YELLOW}ssh-keygen -t ed25519 -C 'github-actions-deploy'${NC}"
echo ""
echo "2. Add the PUBLIC key to this server's authorized_keys:"
echo "   ${YELLOW}nano ~/.ssh/authorized_keys${NC}"
echo ""
echo "3. Add the PRIVATE key to GitHub Secrets as SSH_PRIVATE_KEY"
echo ""
echo "4. Add other required secrets to GitHub (see .github/SECRETS_TEMPLATE.md)"
echo ""
echo "5. Your first deployment will automatically:"
echo "   - Clone the repository to /opt/binance-bot"
echo "   - Build Docker containers"
echo "   - Start all services"
echo ""
echo "6. Monitor deployment logs:"
echo "   ${YELLOW}cd /opt/binance-bot && docker-compose logs -f${NC}"
echo ""
echo "=========================================="
echo ""

# Step 12: Optional - create a reminder file
cat > /opt/binance-bot-setup-complete.txt << EOF
Binance Trading Bot - Server Setup Complete
============================================

Setup Date: $(date)
Server IP: $(hostname -I | awk '{print $1}')

Docker Version: $(docker --version)
Docker Compose Version: $(docker-compose --version)

Project Directory: /opt/binance-bot
Backup Directory: /opt/binance-bot-backups

Next Steps:
1. Configure GitHub Secrets (see .github/SECRETS_TEMPLATE.md)
2. Push to main branch to trigger first deployment
3. Monitor at: cd /opt/binance-bot && docker-compose logs -f

SSH Access:
ssh root@$(hostname -I | awk '{print $1}')

Useful Commands:
- View containers: docker-compose ps
- View logs: docker-compose logs -f
- Restart services: docker-compose restart
- Stop all: docker-compose down
- Start all: docker-compose up -d

For full documentation, see:
- DEPLOYMENT.md
- README.md

============================================
EOF

print_status "Setup complete! Notes saved to: /opt/binance-bot-setup-complete.txt"
echo ""
