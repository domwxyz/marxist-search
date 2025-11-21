#!/bin/bash
#
# Frontend Update Script for Marxist Search Engine
# Usage: sudo ./update_frontend.sh
#
# This script safely updates the frontend by:
# 1. Pulling latest changes from git
# 2. Rebuilding the React app
# 3. Restarting services
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root (use sudo)"
   exit 1
fi

APP_DIR="/opt/marxist-search"
APP_USER="marxist"

# Check if app directory exists
if [ ! -d "$APP_DIR" ]; then
    log_error "Application directory not found: $APP_DIR"
    exit 1
fi

log_info "Starting frontend update process..."

# Step 1: Pull latest changes
log_info "Pulling latest changes from git..."
cd "$APP_DIR"
CURRENT_BRANCH=$(sudo -u $APP_USER git rev-parse --abbrev-ref HEAD)
log_info "Current branch: $CURRENT_BRANCH"

sudo -u $APP_USER git fetch origin
sudo -u $APP_USER git pull origin "$CURRENT_BRANCH"
log_success "Git pull completed"

# Step 2: Rebuild frontend
log_info "Rebuilding frontend..."
cd "$APP_DIR/frontend"

# Check if package.json has changed
if sudo -u $APP_USER git diff --name-only HEAD@{1} HEAD | grep -q "package.json"; then
    log_info "package.json changed, running npm install..."
    sudo -u $APP_USER npm install
else
    log_info "package.json unchanged, skipping npm install"
fi

sudo -u $APP_USER npm run build
log_success "Frontend built successfully"

# Step 3: Restart API service
log_info "Restarting API service..."
systemctl restart marxist-search-api.service
sleep 3
log_success "API service restarted"

# Step 4: Check service status
log_info "Checking service status..."
if systemctl is-active --quiet marxist-search-api.service; then
    log_success "✓ API service is running"
else
    log_error "✗ API service failed to start"
    log_info "Check logs with: journalctl -u marxist-search-api.service -n 50"
    exit 1
fi

if systemctl is-active --quiet marxist-search-update.timer; then
    log_success "✓ Update timer is running"
else
    log_error "✗ Update timer is not running"
fi

# Step 5: Test health endpoint
log_info "Testing health endpoint..."
sleep 2
if curl -s http://localhost:8000/api/v1/health | grep -q "healthy"; then
    log_success "✓ Health check passed"
else
    log_error "✗ Health check failed"
    log_info "Manual check: curl http://localhost:8000/api/v1/health"
fi

echo ""
echo "========================================================================"
echo -e "${GREEN}Frontend Update Complete!${NC}"
echo "========================================================================"
echo ""
echo "Next steps:"
echo "  1. Visit your site and do a hard refresh (Ctrl+Shift+R or Cmd+Shift+R)"
echo "  2. Check if the logo displays correctly"
echo "  3. Test search functionality"
echo ""
echo "Logs:"
echo "  - API logs: tail -f /var/log/news-search/api.log"
echo "  - Error logs: tail -f /var/log/news-search/errors.log"
echo ""
echo "Rollback (if needed):"
echo "  cd $APP_DIR && sudo -u $APP_USER git reset --hard HEAD@{1}"
echo "  cd $APP_DIR/frontend && sudo -u $APP_USER npm run build"
echo "  sudo systemctl restart marxist-search-api.service"
echo ""
echo "========================================================================"
