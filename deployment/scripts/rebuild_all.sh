#!/bin/bash
#
# Complete Rebuild Script for Marxist Search Engine
# Usage: sudo ./rebuild_all.sh
#        or with nohup: sudo nohup ./rebuild_all.sh > /var/log/marxist-search/rebuild.log 2>&1 &
#
# This script performs a complete rebuild:
# 1. Stops all services
# 2. Backs up existing database and index (optional)
# 3. Removes old data
# 4. Initializes new database
# 5. Runs full article archive (1-2 hours)
# 6. Builds search index (3-5 hours)
# 7. Restarts all services
#
# Total runtime: 4-7 hours depending on server performance
#

set -e  # Exit on error

# Configuration
APP_DIR="/opt/marxist-search"
DATA_DIR="/var/lib/marxist-search"
LOG_DIR="/var/log/marxist-search"
APP_USER="marxist"
BACKUP_DIR="${DATA_DIR}/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] [INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] [SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] [WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] [ERROR]${NC} $1"
}

log_step() {
    echo ""
    echo -e "${CYAN}========================================================================"
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] STEP: $1"
    echo -e "========================================================================${NC}"
    echo ""
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root (use sudo)"
   exit 1
fi

# Check if directories exist
if [ ! -d "$APP_DIR" ]; then
    log_error "Application directory not found: $APP_DIR"
    log_info "Please clone the repository to /opt/marxist-search first"
    exit 1
fi

if [ ! -d "$DATA_DIR" ]; then
    log_warning "Data directory not found: $DATA_DIR"
    log_info "Creating data directory..."
    mkdir -p "$DATA_DIR"
    chown -R "$APP_USER:$APP_USER" "$DATA_DIR"
fi

if [ ! -d "$LOG_DIR" ]; then
    log_warning "Log directory not found: $LOG_DIR"
    log_info "Creating log directory..."
    mkdir -p "$LOG_DIR"
    chown -R "$APP_USER:$APP_USER" "$LOG_DIR"
fi

# Banner
clear
echo -e "${CYAN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   MARXIST SEARCH ENGINE - COMPLETE REBUILD SCRIPT            ║
║                                                               ║
║   This will rebuild the entire database and search index.    ║
║   Estimated time: 4-7 hours                                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"
echo ""

log_info "Starting complete rebuild process..."
log_info "Application directory: $APP_DIR"
log_info "Data directory: $DATA_DIR"
log_info "Log directory: $LOG_DIR"
log_info "User: $APP_USER"
echo ""

# Prompt for backup (skip if running non-interactively with nohup)
BACKUP_EXISTING="no"
if [ -t 0 ]; then
    # Running interactively
    if [ -f "$DATA_DIR/articles.db" ]; then
        echo -e "${YELLOW}WARNING: Existing database found!${NC}"
        read -p "Do you want to backup the existing database and index? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            BACKUP_EXISTING="yes"
        fi
    fi
else
    # Running non-interactively (e.g., with nohup)
    log_info "Running non-interactively. Automatic backup will be created if data exists."
    if [ -f "$DATA_DIR/articles.db" ]; then
        BACKUP_EXISTING="yes"
    fi
fi

# ============================================================================
# STEP 1: Stop services
# ============================================================================
log_step "Stopping services"

if systemctl is-active --quiet marxist-search-api.service; then
    log_info "Stopping API service..."
    systemctl stop marxist-search-api.service
    log_success "API service stopped"
else
    log_info "API service is not running"
fi

if systemctl is-active --quiet marxist-search-update.timer; then
    log_info "Stopping update timer..."
    systemctl stop marxist-search-update.timer
    log_success "Update timer stopped"
else
    log_info "Update timer is not running"
fi

# ============================================================================
# STEP 2: Backup existing data (if requested)
# ============================================================================
if [ "$BACKUP_EXISTING" = "yes" ]; then
    log_step "Backing up existing data"

    BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="${BACKUP_DIR}/rebuild_backup_${BACKUP_TIMESTAMP}"

    log_info "Creating backup directory: $BACKUP_PATH"
    mkdir -p "$BACKUP_PATH"

    if [ -f "$DATA_DIR/articles.db" ]; then
        log_info "Backing up database..."
        cp "$DATA_DIR/articles.db" "$BACKUP_PATH/"
        log_success "Database backed up"
    fi

    if [ -d "$DATA_DIR/txtai" ]; then
        log_info "Backing up search index (this may take a while)..."
        cp -r "$DATA_DIR/txtai" "$BACKUP_PATH/"
        log_success "Search index backed up"
    fi

    if [ -d "$DATA_DIR/cache" ]; then
        log_info "Backing up cache..."
        cp -r "$DATA_DIR/cache" "$BACKUP_PATH/"
        log_success "Cache backed up"
    fi

    chown -R "$APP_USER:$APP_USER" "$BACKUP_PATH"
    log_success "Backup completed: $BACKUP_PATH"

    # Clean up old backups (keep last 3)
    log_info "Cleaning up old backups (keeping last 3)..."
    cd "$BACKUP_DIR" 2>/dev/null || true
    ls -t | grep "rebuild_backup_" | tail -n +4 | xargs -r rm -rf
    log_success "Old backups cleaned up"
fi

# ============================================================================
# STEP 3: Clean existing data
# ============================================================================
log_step "Cleaning existing data"

if [ -f "$DATA_DIR/articles.db" ]; then
    log_info "Removing old database..."
    rm -f "$DATA_DIR/articles.db"
    log_success "Old database removed"
fi

if [ -d "$DATA_DIR/txtai" ]; then
    log_info "Removing old search index..."
    rm -rf "$DATA_DIR/txtai"
    log_success "Old search index removed"
fi

if [ -d "$DATA_DIR/cache" ]; then
    log_info "Clearing cache..."
    rm -rf "$DATA_DIR/cache"
    mkdir -p "$DATA_DIR/cache"
    log_success "Cache cleared"
fi

# Ensure data directory structure exists
mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/cache"
chown -R "$APP_USER:$APP_USER" "$DATA_DIR"

# ============================================================================
# STEP 4: Initialize database
# ============================================================================
log_step "Initializing database"

cd "$APP_DIR/backend"
log_info "Running database initialization..."
sudo -u "$APP_USER" DATA_DIR="$DATA_DIR" ../venv/bin/python -m src.cli.marxist_cli init-db
log_success "Database initialized"

# ============================================================================
# STEP 5: Archive all articles
# ============================================================================
log_step "Archiving articles (this will take 1-2 hours)"

START_TIME=$(date +%s)
log_info "Starting full archive run..."
log_info "This will fetch all historical articles from RSS feeds"

sudo -u "$APP_USER" DATA_DIR="$DATA_DIR" ../venv/bin/python -m src.cli.marxist_cli archive run

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
log_success "Archive completed in $MINUTES minutes"

# Check article count
ARTICLE_COUNT=$(sudo -u "$APP_USER" DATA_DIR="$DATA_DIR" ../venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('$DATA_DIR/articles.db')
count = conn.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
print(count)
conn.close()
" 2>/dev/null || echo "0")

log_info "Total articles archived: $ARTICLE_COUNT"

if [ "$ARTICLE_COUNT" -lt 100 ]; then
    log_warning "Warning: Article count seems low ($ARTICLE_COUNT). Expected at least several thousand."
    log_warning "Check the logs for any errors during archiving."
fi

# ============================================================================
# STEP 6: Build search index
# ============================================================================
log_step "Building search index (this will take 3-5 hours)"

START_TIME=$(date +%s)
log_info "Starting index build..."
log_info "This will create vector embeddings for all articles"
log_info "Progress will be logged below..."

sudo -u "$APP_USER" TRANSFORMERS_TRUST_REMOTE_CODE=1 DATA_DIR="$DATA_DIR" ../venv/bin/python -m src.cli.marxist_cli index build

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
HOURS=$((MINUTES / 60))
REMAINING_MINUTES=$((MINUTES % 60))

if [ $HOURS -gt 0 ]; then
    log_success "Index build completed in ${HOURS}h ${REMAINING_MINUTES}m"
else
    log_success "Index build completed in ${MINUTES}m"
fi

# Verify index was created
if [ -d "$DATA_DIR/txtai" ] && [ "$(ls -A $DATA_DIR/txtai)" ]; then
    log_success "Search index created successfully"
else
    log_error "Search index directory is empty or missing!"
    log_error "Index build may have failed. Check logs above."
    exit 1
fi

# ============================================================================
# STEP 7: Set permissions
# ============================================================================
log_step "Setting correct permissions"

chown -R "$APP_USER:$APP_USER" "$DATA_DIR"
log_success "Permissions set"

# ============================================================================
# STEP 8: Start services
# ============================================================================
log_step "Starting services"

log_info "Starting API service..."
systemctl start marxist-search-api.service
sleep 5

if systemctl is-active --quiet marxist-search-api.service; then
    log_success "✓ API service started successfully"
else
    log_error "✗ API service failed to start"
    log_error "Check logs: journalctl -u marxist-search-api.service -n 50"
    exit 1
fi

log_info "Starting update timer..."
systemctl start marxist-search-update.timer

if systemctl is-active --quiet marxist-search-update.timer; then
    log_success "✓ Update timer started successfully"
else
    log_error "✗ Update timer failed to start"
fi

# ============================================================================
# STEP 9: Health check
# ============================================================================
log_step "Running health checks"

log_info "Waiting for API to be ready..."
sleep 5

log_info "Testing health endpoint..."
if curl -s http://localhost:8000/api/v1/health | grep -q "healthy"; then
    log_success "✓ Health check passed"
else
    log_warning "✗ Health check failed or timed out"
    log_info "The API may still be initializing. Check manually: curl http://localhost:8000/api/v1/health"
fi

log_info "Testing search functionality..."
SEARCH_RESULT=$(curl -s "http://localhost:8000/api/v1/search?q=socialism&limit=1" || echo "FAILED")
if echo "$SEARCH_RESULT" | grep -q '"results"'; then
    log_success "✓ Search is working"
else
    log_warning "✗ Search test failed"
    log_info "The index may still be loading. Try again in a few minutes."
fi

# ============================================================================
# FINAL SUMMARY
# ============================================================================
log_step "Rebuild Complete!"

TOTAL_END_TIME=$(date +%s)
TOTAL_DURATION=$((TOTAL_END_TIME - $(date -d "$(date)" +%s)))

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗"
echo -e "║                                                               ║"
echo -e "║   ✓ REBUILD COMPLETED SUCCESSFULLY!                          ║"
echo -e "║                                                               ║"
echo -e "╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Summary:${NC}"
echo "  ✓ Database initialized"
echo "  ✓ Articles archived: $ARTICLE_COUNT"
echo "  ✓ Search index built"
echo "  ✓ Services started"
echo ""
echo -e "${CYAN}Service Status:${NC}"
systemctl status marxist-search-api.service --no-pager -l | head -n 3
systemctl status marxist-search-update.timer --no-pager -l | head -n 3
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo "  1. Test the search functionality in your browser"
echo "  2. Check the logs for any warnings or errors"
echo "  3. Monitor the incremental updates (runs every 30 minutes)"
echo ""
echo -e "${CYAN}Useful Commands:${NC}"
echo "  - View API logs:     tail -f $LOG_DIR/api.log"
echo "  - View error logs:   tail -f $LOG_DIR/errors.log"
echo "  - View service logs: journalctl -u marxist-search-api.service -f"
echo "  - Check service:     systemctl status marxist-search-api.service"
echo "  - Test search:       curl 'http://localhost:8000/api/v1/search?q=test'"
echo ""
if [ "$BACKUP_EXISTING" = "yes" ]; then
    echo -e "${CYAN}Backup Location:${NC}"
    echo "  $BACKUP_PATH"
    echo ""
fi
echo -e "${CYAN}Data Locations:${NC}"
echo "  - Database:     $DATA_DIR/articles.db"
echo "  - Search Index: $DATA_DIR/txtai/"
echo "  - Cache:        $DATA_DIR/cache/"
echo "  - Logs:         $LOG_DIR/"
echo ""
echo "========================================================================"
echo ""
