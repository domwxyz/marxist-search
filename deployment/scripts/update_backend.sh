#!/bin/bash
#
# Backend Update Script for Marxist Search Engine
# Usage: sudo ./update_backend.sh
#
# This script safely updates the backend code by:
# 1. Pulling latest changes from git
# 2. Copying backend files to production
# 3. Installing any new Python dependencies
# 4. Restarting services
#
# NOTE: This does NOT rebuild the database or search index.
# For full rebuilds, see deployment_guide.txt
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

REPO_DIR="/opt/marxist-search-repo"
APP_DIR="/opt/marxist-search"
APP_USER="marxist"

# Check if directories exist
if [ ! -d "$REPO_DIR" ]; then
    log_error "Repository directory not found: $REPO_DIR"
    log_info "Move your repo from /tmp: sudo mv /tmp/marxist-search /opt/marxist-search-repo"
    exit 1
fi

if [ ! -d "$APP_DIR" ]; then
    log_error "Application directory not found: $APP_DIR"
    exit 1
fi

log_info "Starting backend update process..."
log_info "Repository: $REPO_DIR"
log_info "Production: $APP_DIR"

# Step 1: Pull latest changes in repo
log_info "Pulling latest changes from git..."
cd "$REPO_DIR"
CURRENT_BRANCH=$(sudo -u $APP_USER git rev-parse --abbrev-ref HEAD)
log_info "Current branch: $CURRENT_BRANCH"

sudo -u $APP_USER git fetch origin
sudo -u $APP_USER git pull origin "$CURRENT_BRANCH"
log_success "Git pull completed"

# Step 2: Copy updated backend to production
log_info "Copying backend files to production..."

# Copy Python source code
cp -r "$REPO_DIR/backend/src" "$APP_DIR/backend/"

# Copy config files (but preserve .env)
cp -r "$REPO_DIR/backend/config"/* "$APP_DIR/backend/config/"

# Update requirements.txt
cp "$REPO_DIR/backend/requirements.txt" "$APP_DIR/backend/"

# Preserve ownership
chown -R "$APP_USER:$APP_USER" "$APP_DIR/backend/src"
chown -R "$APP_USER:$APP_USER" "$APP_DIR/backend/config"
chown "$APP_USER:$APP_USER" "$APP_DIR/backend/requirements.txt"

log_success "Files copied"

# Step 3: Check for dependency changes
log_info "Checking for dependency changes..."
cd "$APP_DIR/backend"

if [ -f "$REPO_DIR/.git/ORIG_HEAD" ]; then
    if sudo -u $APP_USER git -C "$REPO_DIR" diff --name-only ORIG_HEAD HEAD | grep -q "requirements.txt"; then
        log_info "requirements.txt changed, installing new dependencies..."
        sudo -u $APP_USER venv/bin/pip install --upgrade pip
        sudo -u $APP_USER venv/bin/pip install -r requirements.txt
        log_success "Dependencies updated"
    else
        log_info "requirements.txt unchanged, skipping dependency install"
    fi
else
    log_warning "Cannot detect if requirements.txt changed, skipping dependency install"
    log_info "To manually install: cd $APP_DIR/backend && sudo -u $APP_USER venv/bin/pip install -r requirements.txt"
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
echo "  - Python source code (backend/src/)"
echo "  - Configuration files (backend/config/)"
echo "  - Dependencies (if requirements.txt changed)"
echo ""
echo "NOT updated:"
echo "  - Database (backend/data/articles.db)"
echo "  - Search index (backend/data/txtai/)"
echo "  - Environment file (backend/.env)"
echo ""
echo "Next steps:"
echo "  1. Test your API changes"
echo "  2. Check the logs for any errors"
echo "  3. If needed, rebuild index: cd $APP_DIR/backend && sudo -u $APP_USER venv/bin/python -m src.cli.marxist_cli index update"
echo ""
echo "Logs:"
echo "  - API logs: tail -f /var/log/news-search/api.log"
echo "  - Error logs: tail -f /var/log/news-search/errors.log"
echo "  - Service logs: journalctl -u marxist-search-api.service -f"
echo ""
echo "Rollback (if needed):"
echo "  cd $REPO_DIR && sudo -u $APP_USER git reset --hard HEAD@{1}"
echo "  cd $REPO_DIR && sudo ./deployment/scripts/update_backend.sh"
echo ""
echo "========================================================================"
