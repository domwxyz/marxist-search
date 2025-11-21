#!/bin/bash
#
# Deployment script for Marxist Search Engine
# Usage: cd deployment && sudo ./deploy.sh <domain>
#
# This script automates the deployment of the Marxist Search Engine
# to a Linux VPS (DigitalOcean, Linode, etc.)
#

set -e  # Exit on error

# ============================================================================
# Configuration
# ============================================================================

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

DOMAIN="${1:-YOUR_DOMAIN_HERE}"
APP_DIR="/opt/marxist-search"
DATA_DIR="/var/lib/marxist-search"
LOG_DIR="/var/log/news-search"
APP_USER="marxist"
APP_GROUP="marxist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ============================================================================
# Validation
# ============================================================================

check_root

if [ "$DOMAIN" = "YOUR_DOMAIN_HERE" ]; then
    log_error "Please provide a domain name as the first argument"
    echo "Usage: sudo ./deploy.sh yourdomain.com"
    exit 1
fi

log_info "Deploying Marxist Search Engine for domain: $DOMAIN"
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warning "Deployment cancelled"
    exit 0
fi

# ============================================================================
# System Dependencies
# ============================================================================

log_info "Installing system dependencies..."

# Detect available Python 3 version
PYTHON_CMD=""
for version in 3.12 3.11 3.10 3.9; do
    if command_exists "python$version"; then
        PYTHON_CMD="python$version"
        PYTHON_VERSION="$version"
        log_info "Found Python $version"
        break
    fi
done

# If no specific version found, check for python3
if [ -z "$PYTHON_CMD" ]; then
    if command_exists python3; then
        PYTHON_CMD="python3"
        PYTHON_VERSION=$(python3 --version | awk '{print $2}' | cut -d. -f1,2)
        log_info "Using system python3 (version $PYTHON_VERSION)"
    else
        log_error "No Python 3 installation found!"
        exit 1
    fi
fi

# Check if Python version is sufficient (>= 3.9)
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
    log_error "Python 3.9 or higher is required. Found: $PYTHON_VERSION"
    exit 1
fi

log_success "Using Python $PYTHON_VERSION at $(which $PYTHON_CMD)"

apt-get update
apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    nginx \
    git \
    curl \
    build-essential \
    certbot \
    python3-certbot-nginx

log_success "System dependencies installed"

# ============================================================================
# Create Application User
# ============================================================================

log_info "Creating application user..."

if id "$APP_USER" &>/dev/null; then
    log_warning "User $APP_USER already exists"
else
    useradd --system --shell /bin/bash --home-dir "$APP_DIR" --create-home "$APP_USER"
    log_success "User $APP_USER created"
fi

# ============================================================================
# Create Directory Structure
# ============================================================================

log_info "Creating directory structure..."

mkdir -p "$APP_DIR"
mkdir -p "$DATA_DIR"/{txtai,cache}
mkdir -p "$LOG_DIR"

# Set ownership
chown -R "$APP_USER:$APP_GROUP" "$APP_DIR"
chown -R "$APP_USER:$APP_GROUP" "$DATA_DIR"
chown -R "$APP_USER:$APP_GROUP" "$LOG_DIR"

# Set permissions
chmod 755 "$APP_DIR"
chmod 755 "$DATA_DIR"
chmod 755 "$LOG_DIR"

log_success "Directory structure created"

# ============================================================================
# Copy Application Files
# ============================================================================

log_info "Copying application files..."

# Copy from project root
cp -r "$PROJECT_ROOT/backend" "$APP_DIR/"
cp -r "$PROJECT_ROOT/frontend" "$APP_DIR/"

# Copy configuration files if they don't exist
if [ ! -f "$APP_DIR/backend/.env" ]; then
    cp "$SCRIPT_DIR/.env.production.example" "$APP_DIR/backend/.env"

    # Set CORS origins with the domain
    sed -i "s|# ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com|ALLOWED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN,http://$DOMAIN,http://www.$DOMAIN|g" "$APP_DIR/backend/.env"

    log_success "Created .env file with CORS configured for $DOMAIN"
else
    log_warning ".env file already exists - skipping"
fi

chown -R "$APP_USER:$APP_GROUP" "$APP_DIR"

log_success "Application files copied"

# ============================================================================
# Python Virtual Environment
# ============================================================================

log_info "Setting up Python virtual environment..."

cd "$APP_DIR/backend"

# Create venv as app user using detected Python version
log_info "Creating virtual environment with $PYTHON_CMD..."
sudo -u "$APP_USER" "$PYTHON_CMD" -m venv venv

# Verify venv was created successfully
if [ ! -f "venv/bin/python" ]; then
    log_error "Failed to create virtual environment"
    exit 1
fi

# Install dependencies
log_info "Installing Python dependencies..."
sudo -u "$APP_USER" venv/bin/pip install --upgrade pip setuptools wheel
sudo -u "$APP_USER" venv/bin/pip install -r requirements.txt

log_success "Python environment configured with $(venv/bin/python --version)"

# ============================================================================
# Frontend Build
# ============================================================================

log_info "Building frontend..."

cd "$APP_DIR/frontend"

if ! command_exists node; then
    log_warning "Node.js not found, installing..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# Install and build as app user
sudo -u "$APP_USER" npm install
sudo -u "$APP_USER" npm run build

log_success "Frontend built"

# ============================================================================
# Nginx Configuration
# ============================================================================

log_info "Configuring Nginx..."

# Copy nginx config from deployment directory
cp "$SCRIPT_DIR/nginx.conf" /etc/nginx/sites-available/marxist-search

# Replace domain placeholder
sed -i "s/YOUR_DOMAIN_HERE/$DOMAIN/g" /etc/nginx/sites-available/marxist-search

# Enable site
ln -sf /etc/nginx/sites-available/marxist-search /etc/nginx/sites-enabled/

# Test nginx config
if nginx -t; then
    log_success "Nginx configuration valid"
else
    log_error "Nginx configuration invalid"
    exit 1
fi

# Reload nginx
systemctl reload nginx

log_success "Nginx configured"

# ============================================================================
# Systemd Services
# ============================================================================

log_info "Installing systemd services..."

# Copy service files from deployment directory
cp "$SCRIPT_DIR/systemd/marxist-search-api.service" /etc/systemd/system/
cp "$SCRIPT_DIR/systemd/marxist-search-update.service" /etc/systemd/system/
cp "$SCRIPT_DIR/systemd/marxist-search-update.timer" /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable and start API service
systemctl enable marxist-search-api.service
systemctl start marxist-search-api.service

# Enable and start update timer
systemctl enable marxist-search-update.timer
systemctl start marxist-search-update.timer

log_success "Systemd services installed and started"

# ============================================================================
# SSL Certificate (Let's Encrypt)
# ============================================================================

log_info "Setting up SSL certificate..."

read -p "Do you want to set up SSL with Let's Encrypt? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email
    log_success "SSL certificate installed"

    # Uncomment HTTPS section in nginx config
    sed -i 's/# server {/server {/g; s/#     /    /g; s/#}/}/g' /etc/nginx/sites-available/marxist-search
    sed -i "s/YOUR_DOMAIN_HERE/$DOMAIN/g" /etc/nginx/sites-available/marxist-search

    # Enable HTTP->HTTPS redirect
    sed -i 's/# return 301/return 301/g' /etc/nginx/sites-available/marxist-search

    systemctl reload nginx
else
    log_warning "Skipping SSL setup"
fi

# ============================================================================
# Firewall Configuration
# ============================================================================

log_info "Configuring firewall..."

if command_exists ufw; then
    ufw allow 22/tcp    # SSH
    ufw allow 80/tcp    # HTTP
    ufw allow 443/tcp   # HTTPS
    ufw --force enable
    log_success "Firewall configured"
else
    log_warning "UFW not found, skipping firewall configuration"
fi

# ============================================================================
# Log Rotation
# ============================================================================

log_info "Setting up log rotation..."

cat > /etc/logrotate.d/marxist-search <<EOF
/var/log/news-search/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 $APP_USER $APP_GROUP
    sharedscripts
    postrotate
        systemctl reload marxist-search-api.service > /dev/null 2>&1 || true
    endscript
}
EOF

log_success "Log rotation configured"

# ============================================================================
# Status Check
# ============================================================================

log_info "Checking service status..."

sleep 3

if systemctl is-active --quiet marxist-search-api.service; then
    log_success "API service is running"
else
    log_error "API service failed to start"
    log_info "Check logs: journalctl -u marxist-search-api.service -n 50"
fi

if systemctl is-active --quiet marxist-search-update.timer; then
    log_success "Update timer is active"
else
    log_warning "Update timer is not active"
fi

# Test API health endpoint
sleep 2
if curl -s http://localhost:8000/api/v1/health > /dev/null; then
    log_success "API health check passed"
else
    log_warning "API health check failed"
fi

# ============================================================================
# Summary
# ============================================================================

echo ""
echo "========================================================================"
echo -e "${GREEN}Deployment Complete!${NC}"
echo "========================================================================"
echo ""
echo "Application directory: $APP_DIR"
echo "Data directory: $DATA_DIR"
echo "Log directory: $LOG_DIR"
echo ""
echo "Services:"
echo "  - API: systemctl status marxist-search-api"
echo "  - Update Timer: systemctl status marxist-search-update.timer"
echo ""
echo "Logs:"
echo "  - API: tail -f /var/log/news-search/api.log"
echo "  - Updates: tail -f /var/log/news-search/ingestion.log"
echo "  - Errors: tail -f /var/log/news-search/errors.log"
echo ""
echo "Next steps:"
echo "  1. Configure /opt/marxist-search/backend/.env"
echo "  2. Initialize database: cd $APP_DIR/backend && sudo -u $APP_USER venv/bin/python -m src.cli.marxist_cli init-db"
echo "  3. Run initial archiving: sudo -u $APP_USER venv/bin/python -m src.cli.marxist_cli archive run"
echo "  4. Build index: sudo -u $APP_USER venv/bin/python -m src.cli.marxist_cli index build"
echo "  5. Restart API: systemctl restart marxist-search-api"
echo ""
echo "Website: http://$DOMAIN (or https://$DOMAIN if SSL was configured)"
echo ""
echo "========================================================================"
