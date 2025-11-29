#!/bin/bash
#
# Deploy Systemd Service Files
# Usage: sudo ./deploy_systemd.sh
#
# This script safely deploys the systemd service files from the repo
# to /etc/systemd/system/ with proper verification.
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SYSTEMD_SOURCE="$REPO_ROOT/deployment/systemd"

log_info "Systemd Service Deployment Script"
log_info "Repository: $REPO_ROOT"
log_info "Source: $SYSTEMD_SOURCE"
echo ""

# Verify source files exist
if [ ! -d "$SYSTEMD_SOURCE" ]; then
    log_error "Systemd source directory not found: $SYSTEMD_SOURCE"
    exit 1
fi

log_info "Checking source files..."
REQUIRED_FILES=(
    "marxist-search-api.service"
    "marxist-search-update.service"
    "marxist-search-update.timer"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$SYSTEMD_SOURCE/$file" ]; then
        log_error "Required file missing: $file"
        exit 1
    fi
    log_success "Found: $file"
done

echo ""
log_info "Verifying source files are clean..."

# Check for trust_remote_code
if grep -qi "trust_remote_code" "$SYSTEMD_SOURCE"/*.service 2>/dev/null; then
    log_error "FOUND trust_remote_code in source files! Cannot deploy."
    grep -n "trust_remote_code" "$SYSTEMD_SOURCE"/*.service
    exit 1
fi
log_success "✓ No trust_remote_code found"

# Check for download_model
if grep -qi "download_model" "$SYSTEMD_SOURCE"/*.service 2>/dev/null; then
    log_error "FOUND download_model in source files! Cannot deploy."
    grep -n "download_model" "$SYSTEMD_SOURCE"/*.service
    exit 1
fi
log_success "✓ No download_model references found"

echo ""
log_info "Stopping existing services..."

# Stop services if they're running
if systemctl is-active --quiet marxist-search-api.service 2>/dev/null; then
    systemctl stop marxist-search-api.service
    log_success "Stopped API service"
else
    log_info "API service not running"
fi

if systemctl is-active --quiet marxist-search-update.timer 2>/dev/null; then
    systemctl stop marxist-search-update.timer
    log_success "Stopped update timer"
else
    log_info "Update timer not running"
fi

echo ""
log_info "Copying service files to /etc/systemd/system/..."

for file in "${REQUIRED_FILES[@]}"; do
    cp "$SYSTEMD_SOURCE/$file" "/etc/systemd/system/"
    chmod 644 "/etc/systemd/system/$file"
    log_success "Deployed: $file"
done

echo ""
log_info "Reloading systemd daemon..."
systemctl daemon-reload
log_success "Daemon reloaded"

echo ""
log_info "Verifying installed files..."

# Verify files were copied correctly
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "/etc/systemd/system/$file" ]; then
        log_error "File not found after copy: /etc/systemd/system/$file"
        exit 1
    fi
done
log_success "All files verified in /etc/systemd/system/"

# Check for trust_remote_code in installed files
if grep -qi "trust_remote_code" /etc/systemd/system/marxist-search*.service 2>/dev/null; then
    log_error "FOUND trust_remote_code in installed files!"
    grep -n "trust_remote_code" /etc/systemd/system/marxist-search*.service
    exit 1
fi
log_success "✓ Installed files are clean (no trust_remote_code)"

# Verify systemd can parse the files
log_info "Validating systemd syntax..."
for file in "${REQUIRED_FILES[@]}"; do
    if systemctl cat "$file" > /dev/null 2>&1; then
        log_success "✓ $file syntax valid"
    else
        log_error "✗ $file syntax error"
        exit 1
    fi
done

echo ""
log_info "Enabling services..."
systemctl enable marxist-search-api.service
systemctl enable marxist-search-update.timer
log_success "Services enabled"

echo ""
log_warning "Services are installed and enabled but NOT started"
log_info "To start services, run:"
echo "  sudo systemctl start marxist-search-api.service"
echo "  sudo systemctl start marxist-search-update.timer"
echo ""
log_info "To check status:"
echo "  sudo systemctl status marxist-search-api.service"
echo "  sudo systemctl status marxist-search-update.timer"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Systemd Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Deployed services:"
echo "  - marxist-search-api.service"
echo "  - marxist-search-update.service"
echo "  - marxist-search-update.timer"
echo ""
echo "Location: /etc/systemd/system/"
echo ""
