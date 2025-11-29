#!/bin/bash
#
# Backend Update Script for Marxist Search Engine
# Usage: sudo ./update_backend.sh [branch_name]
#
# This script safely updates the backend code by:
# 1. Pulling latest changes from git
# 2. Installing any new Python dependencies
# 3. Restarting services
#
# NOTE: This does NOT rebuild the database or search index.
# For full rebuilds, use: sudo ./rebuild_all.sh
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

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
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
BRANCH="${1:-main}"  # Default to main branch if not specified

# Check if directory exists
if [ ! -d "$APP_DIR" ]; then
    log_error "Application directory not found: $APP_DIR"
    log_info "Please clone the repository to /opt/marxist-search first"
    exit 1
fi

if [ ! -d "$APP_DIR/.git" ]; then
    log_error "$APP_DIR is not a git repository"
    log_info "Please ensure /opt/marxist-search is a git clone, not a copied directory"
    exit 1
fi

log_info "Starting backend update process..."
log_info "Application directory: $APP_DIR"
log_info "Target branch: $BRANCH"

# Step 1: Pull latest changes
log_info "Pulling latest changes from git..."
cd "$APP_DIR"

CURRENT_BRANCH=$(sudo -u $APP_USER git rev-parse --abbrev-ref HEAD)
log_info "Current branch: $CURRENT_BRANCH"

# Stash any local changes (shouldn't be any in production)
if ! sudo -u $APP_USER git diff --quiet; then
    log_warning "Local changes detected, stashing..."
    sudo -u $APP_USER git stash
fi

sudo -u $APP_USER git fetch origin
sudo -u $APP_USER git pull origin "$BRANCH"
log_success "Git pull completed"

# Step 2: Check for dependency changes
log_info "Checking for dependency changes..."
cd "$APP_DIR/backend"

if [ -f "$APP_DIR/.git/ORIG_HEAD" ]; then
    if sudo -u $APP_USER git -C "$APP_DIR" diff --name-only ORIG_HEAD HEAD | grep -q "backend/requirements.txt"; then
        log_info "requirements.txt changed, installing new dependencies..."
        sudo -u $APP_USER ../venv/bin/pip install --upgrade pip
        sudo -u $APP_USER ../venv/bin/pip install -r requirements.txt
        log_success "Dependencies updated"
    else
        log_info "requirements.txt unchanged, skipping dependency install"
    fi
else
    log_warning "Cannot detect if requirements.txt changed"
    log_info "To manually install: cd $APP_DIR/backend && sudo -u $APP_USER ../venv/bin/pip install -r requirements.txt"
fi

# Step 4: Restart services
log_info "Restarting API service..."
systemctl restart marxist-search-api.service
sleep 3
log_success "API service restarted"

# Step 5: Check service status
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
    log_warning "✗ Update timer is not running"
fi

# Step 6: Test health endpoint
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
echo -e "${GREEN}Backend Update Complete!${NC}"
echo "========================================================================"
echo ""
echo "Updated:"
echo "  - Backend code (backend/)"
echo "  - Dependencies (if requirements.txt changed)"
echo ""
echo "NOT updated:"
echo "  - Database (/var/lib/marxist-search/articles.db)"
echo "  - Search index (/var/lib/marxist-search/txtai/)"
echo ""
echo "Next steps:"
echo "  1. Test your API changes"
echo "  2. Check the logs for any errors"
echo "  3. If needed, rebuild index: cd $APP_DIR/backend && sudo -u $APP_USER ../venv/bin/python -m src.cli.marxist_cli index update"
echo ""
echo "Logs:"
echo "  - API logs: tail -f /var/log/marxist-search/api.log"
echo "  - Error logs: tail -f /var/log/marxist-search/errors.log"
echo "  - Service logs: journalctl -u marxist-search-api.service -f"
echo ""
echo "Rollback (if needed):"
echo "  cd $APP_DIR && sudo -u $APP_USER git reset --hard HEAD@{1}"
echo "  sudo ./deployment/scripts/update_backend.sh"
echo ""
echo "========================================================================"
