#!/bin/bash
#
# Rebuild Index Script for Marxist Search Engine
# Usage: sudo ./rebuild_index.sh
#        or with nohup: sudo nohup ./rebuild_index.sh > /var/log/marxist-search/rebuild_index.log 2>&1 &
#
# This script rebuilds ONLY the search index from an existing database:
# 1. Stops services
# 2. Backs up existing index (optional)
# 3. Removes old index
# 4. Builds new search index from existing database (3-5 hours)
# 5. Restarts services
#
# Use this when:
# - Testing a new model
# - Upgrading the embedding model
# - Index is corrupted
# - Database already exists and is up-to-date
#
# For a full rebuild (database + index), use: sudo ./rebuild_all.sh
#
# Total runtime: 3-5 hours depending on server performance
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
    log_error "Data directory not found: $DATA_DIR"
    exit 1
fi

# Check if database exists
if [ ! -f "$DATA_DIR/articles.db" ]; then
    log_error "Database not found: $DATA_DIR/articles.db"
    log_info "You need to run the full rebuild first: sudo ./rebuild_all.sh"
    exit 1
fi

# Banner
clear
echo -e "${CYAN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   MARXIST SEARCH ENGINE - INDEX REBUILD SCRIPT               ║
║                                                               ║
║   This will rebuild the search index from existing database. ║
║   Estimated time: 3-5 hours                                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"
echo ""

log_info "Starting index rebuild process..."
log_info "Application directory: $APP_DIR"
log_info "Data directory: $DATA_DIR"
log_info "Database: $DATA_DIR/articles.db"
log_info "User: $APP_USER"
echo ""

# Check article count in database
ARTICLE_COUNT=$(sudo -u "$APP_USER" sqlite3 "$DATA_DIR/articles.db" "SELECT COUNT(*) FROM articles;" 2>/dev/null || echo "0")
log_info "Articles in database: $ARTICLE_COUNT"

if [ "$ARTICLE_COUNT" -eq 0 ]; then
    log_warning "Database has 0 articles! You may need to run the full rebuild: sudo ./rebuild_all.sh"
fi

# Prompt for backup (skip if running non-interactively with nohup)
BACKUP_EXISTING="no"
if [ -t 0 ]; then
    # Running interactively
    if [ -d "$DATA_DIR/txtai" ]; then
        echo -e "${YELLOW}WARNING: Existing index found!${NC}"
        read -p "Do you want to backup the existing index? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            BACKUP_EXISTING="yes"
        fi
    fi
else
    # Running non-interactively (e.g., with nohup)
    log_info "Running non-interactively. Automatic backup will be created if index exists."
    if [ -d "$DATA_DIR/txtai" ]; then
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
# STEP 2: Backup existing index (if requested)
# ============================================================================
if [ "$BACKUP_EXISTING" = "yes" ]; then
    log_step "Backing up existing index"

    BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="${BACKUP_DIR}/index_backup_${BACKUP_TIMESTAMP}"

    log_info "Creating backup directory: $BACKUP_PATH"
    mkdir -p "$BACKUP_PATH"

    if [ -d "$DATA_DIR/txtai" ]; then
        log_info "Backing up search index (this may take a while)..."
        cp -r "$DATA_DIR/txtai" "$BACKUP_PATH/"
        log_success "Search index backed up"
    fi

    chown -R "$APP_USER:$APP_USER" "$BACKUP_PATH"
    log_success "Backup completed: $BACKUP_PATH"

    # Clean up old backups (keep last 3)
    log_info "Cleaning up old backups (keeping last 3)..."
    cd "$BACKUP_DIR" 2>/dev/null || true
    ls -t | grep "index_backup_" | tail -n +4 | xargs -r rm -rf
    log_success "Old backups cleaned up"
fi

# ============================================================================
# STEP 3: Remove old index
# ============================================================================
log_step "Removing old index"

if [ -d "$DATA_DIR/txtai" ]; then
    log_info "Removing old search index..."
    rm -rf "$DATA_DIR/txtai"
    log_success "Old search index removed"
else
    log_info "No existing index found"
fi

# Ensure data directory structure exists
mkdir -p "$DATA_DIR/txtai"
chown -R "$APP_USER:$APP_USER" "$DATA_DIR"

# ============================================================================
# STEP 4: Build search index
# ============================================================================
log_step "Building search index (this will take 3-5 hours)"

START_TIME=$(date +%s)
log_info "Starting index build..."
log_info "This will create vector embeddings for $ARTICLE_COUNT articles"
log_info "Progress will be logged below..."
echo ""

cd "$APP_DIR/backend"
sudo -u "$APP_USER" DATA_DIR="$DATA_DIR" ../venv/bin/python -m src.cli.marxist_cli index build

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
    INDEX_SIZE=$(du -sh "$DATA_DIR/txtai" | awk '{print $1}')
    log_success "Search index created successfully (size: $INDEX_SIZE)"
else
    log_error "Search index directory is empty or missing!"
    log_error "Index build may have failed. Check logs above."
    exit 1
fi

# ============================================================================
# STEP 5: Set permissions
# ============================================================================
log_step "Setting correct permissions"

chown -R "$APP_USER:$APP_USER" "$DATA_DIR/txtai"
log_success "Permissions set"

# ============================================================================
# STEP 6: Start services
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
# STEP 7: Health check
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
log_step "Index Rebuild Complete!"

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗"
echo -e "║                                                               ║"
echo -e "║   ✓ INDEX REBUILD COMPLETED SUCCESSFULLY!                    ║"
echo -e "║                                                               ║"
echo -e "╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Summary:${NC}"
echo "  ✓ Search index rebuilt"
echo "  ✓ Articles indexed: $ARTICLE_COUNT"
echo "  ✓ Services started"
if [ $HOURS -gt 0 ]; then
    echo "  ✓ Total time: ${HOURS}h ${REMAINING_MINUTES}m"
else
    echo "  ✓ Total time: ${MINUTES}m"
fi
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
echo "  - Database:     $DATA_DIR/articles.db ($ARTICLE_COUNT articles)"
echo "  - Search Index: $DATA_DIR/txtai/ ($INDEX_SIZE)"
echo "  - Logs:         $LOG_DIR/"
echo ""
echo "========================================================================"
echo ""
