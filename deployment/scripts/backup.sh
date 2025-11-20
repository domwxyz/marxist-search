#!/bin/bash
#
# Backup script for Marxist Search Engine
# Usage: ./backup.sh
#
# This script creates backups of the database, index, and configuration
# Should be run as the marxist user or root
#

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/var/backups/marxist-search}"
DATA_DIR="${DATA_DIR:-/var/lib/marxist-search}"
APP_DIR="${APP_DIR:-/opt/marxist-search}"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================="
echo "Marxist Search Engine - Backup Script"
echo "========================================="
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup database
echo -e "${GREEN}Backing up database...${NC}"
cp "$DATA_DIR/articles.db" "$BACKUP_DIR/articles-$DATE.db"
echo "  -> $BACKUP_DIR/articles-$DATE.db"

# Backup configuration
echo -e "${GREEN}Backing up configuration...${NC}"
tar -czf "$BACKUP_DIR/config-$DATE.tar.gz" \
    -C "$APP_DIR/backend" config/ .env 2>/dev/null || true
echo "  -> $BACKUP_DIR/config-$DATE.tar.gz"

# Optional: Backup index (large file)
read -p "Backup txtai index? (takes time, large file) [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}Backing up txtai index...${NC}"
    tar -czf "$BACKUP_DIR/txtai-$DATE.tar.gz" \
        -C "$DATA_DIR" txtai/
    echo "  -> $BACKUP_DIR/txtai-$DATE.tar.gz"
fi

# Clean old backups
echo -e "${GREEN}Cleaning old backups (older than $RETENTION_DAYS days)...${NC}"
find "$BACKUP_DIR" -type f -mtime +$RETENTION_DAYS -delete

# Summary
echo ""
echo "========================================="
echo "Backup complete!"
echo "========================================="
echo "Location: $BACKUP_DIR"
ls -lh "$BACKUP_DIR" | grep "$DATE"
echo ""
