# Marxist Search Engine - Simplified Deployment Guide v2

This guide covers the new simplified deployment structure with single repository location and streamlined rebuild process.

## Table of Contents
- [Quick Start](#quick-start)
- [New Directory Structure](#new-directory-structure)
- [Initial Setup](#initial-setup)
- [Rebuild Process](#rebuild-process)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)

## Key Changes from Previous Deployment

**Old Structure:**
- `/opt/marxist-search-repo` (git repository)
- `/opt/marxist-search` (production copy)
- Manual file copying required
- Environment variables needed for builds

**New Structure:**
- `/opt/marxist-search` (single git repository - everything in one place)
- No copying required
- No environment variable exports needed
- All configuration in systemd services

## Quick Start

For an upgrade from the old structure:

```bash
# 1. Backup your data (optional but recommended)
sudo mkdir -p /var/lib/marxist-search/backups/manual_backup
sudo cp /var/lib/marxist-search/articles.db /var/lib/marxist-search/backups/manual_backup/
sudo cp -r /var/lib/marxist-search/txtai /var/lib/marxist-search/backups/manual_backup/

# 2. Remove old directories
sudo systemctl stop marxist-search-api.service marxist-search-update.timer
sudo rm -rf /opt/marxist-search-repo /opt/marxist-search

# 3. Clone repository to new location
sudo git clone https://github.com/domwxyz/marxist-search.git /opt/marxist-search
cd /opt/marxist-search
sudo git checkout main  # or your desired branch

# 4. Create marxist user (if not exists)
sudo useradd -r -s /bin/bash -d /opt/marxist-search -m marxist || true

# 5. Set ownership
sudo chown -R marxist:marxist /opt/marxist-search
sudo chown -R marxist:marxist /var/lib/marxist-search

# 6. Create log directory
sudo mkdir -p /var/log/marxist-search
sudo chown -R marxist:marxist /var/log/marxist-search

# 7. Create Python virtual environment
cd /opt/marxist-search
sudo -u marxist python3 -m venv venv
sudo -u marxist venv/bin/pip install --upgrade pip
sudo -u marxist venv/bin/pip install -r backend/requirements.txt

# 8. Build frontend
cd /opt/marxist-search/frontend
sudo -u marxist npm install
sudo -u marxist npm run build

# 9. Update systemd service files
sudo cp /opt/marxist-search/deployment/systemd/*.service /etc/systemd/system/
sudo cp /opt/marxist-search/deployment/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload

# 10. Run the rebuild script (can use nohup for background execution)
cd /opt/marxist-search/deployment/scripts
sudo nohup ./rebuild_all.sh > /var/log/marxist-search/rebuild.log 2>&1 &

# Monitor progress
tail -f /var/log/marxist-search/rebuild.log
```

## New Directory Structure

```
/opt/marxist-search/                    # Single git repository
├── backend/
│   ├── src/                           # Python source code
│   ├── config/                        # Configuration files
│   ├── requirements.txt               # Python dependencies
│   └── (no venv here)
├── frontend/
│   ├── src/                           # React source
│   ├── build/                         # Built static files (nginx serves these)
│   └── package.json
├── deployment/
│   ├── systemd/                       # Service files
│   ├── scripts/                       # Maintenance scripts
│   │   ├── rebuild_all.sh            # NEW: Complete rebuild script
│   │   ├── update_backend.sh         # Updated for new structure
│   │   ├── update_frontend.sh        # Updated for new structure
│   │   ├── backup.sh
│   │   └── health_check.sh
│   └── nginx.conf
└── venv/                              # NEW: Virtual environment at root level

/var/lib/marxist-search/               # Data directory (unchanged)
├── articles.db                        # SQLite database
├── txtai/                             # Search index
├── cache/                             # Application cache
└── backups/                           # Automatic backups

/var/log/marxist-search/               # Logs (renamed from news-search)
├── api.log
├── errors.log
├── ingestion.log
└── rebuild.log                        # From rebuild_all.sh
```

## Initial Setup

### Prerequisites

```bash
# Install system dependencies
sudo apt update
sudo apt install -y python3.9 python3.9-venv python3-pip \
    nginx nodejs npm git curl sqlite3

# Install certbot for SSL (optional)
sudo apt install -y certbot python3-certbot-nginx
```

### Clone Repository

```bash
# Clone to the new single location
sudo git clone https://github.com/domwxyz/marxist-search.git /opt/marxist-search
cd /opt/marxist-search
```

### Create System User

```bash
# Create marxist user with home directory at /opt/marxist-search
sudo useradd -r -s /bin/bash -d /opt/marxist-search marxist || true
sudo chown -R marxist:marxist /opt/marxist-search
```

### Create Data and Log Directories

```bash
# Data directory
sudo mkdir -p /var/lib/marxist-search/{cache,backups}
sudo chown -R marxist:marxist /var/lib/marxist-search

# Log directory (note: marxist-search, not news-search)
sudo mkdir -p /var/log/marxist-search
sudo chown -R marxist:marxist /var/log/marxist-search
```

### Setup Python Environment

```bash
cd /opt/marxist-search
sudo -u marxist python3 -m venv venv
sudo -u marxist venv/bin/pip install --upgrade pip
sudo -u marxist venv/bin/pip install -r backend/requirements.txt
```

### Build Frontend

```bash
cd /opt/marxist-search/frontend
sudo -u marxist npm install
sudo -u marxist npm run build
```

### Configure Nginx

```bash
# Copy nginx configuration
sudo cp /opt/marxist-search/deployment/nginx.conf /etc/nginx/sites-available/marxist-search
sudo ln -s /etc/nginx/sites-available/marxist-search /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove default site

# Test configuration
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### Install Systemd Services

```bash
# Copy service files
sudo cp /opt/marxist-search/deployment/systemd/*.service /etc/systemd/system/
sudo cp /opt/marxist-search/deployment/systemd/*.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services (don't start yet - rebuild script will do this)
sudo systemctl enable marxist-search-api.service
sudo systemctl enable marxist-search-update.timer
```

## Rebuild Process

### NEW: Single Script Rebuild

The new `rebuild_all.sh` script handles everything:
- Stops services
- Backs up existing data (optional)
- Removes old database and index
- Initializes new database
- Archives all articles (1-2 hours)
- Builds search index (3-5 hours)
- Restarts services
- Runs health checks

**Interactive mode:**
```bash
cd /opt/marxist-search/deployment/scripts
sudo ./rebuild_all.sh
```

**Background mode (recommended for long rebuilds):**
```bash
cd /opt/marxist-search/deployment/scripts
sudo nohup ./rebuild_all.sh > /var/log/marxist-search/rebuild.log 2>&1 &

# Monitor progress in another terminal
tail -f /var/log/marxist-search/rebuild.log

# Or check if it's still running
ps aux | grep rebuild_all.sh
```

**Total runtime:** 4-7 hours depending on server performance

### Manual Step-by-Step (if needed)

If you prefer manual control:

```bash
# 1. Stop services
sudo systemctl stop marxist-search-api.service
sudo systemctl stop marxist-search-update.timer

# 2. Backup (optional)
sudo mkdir -p /var/lib/marxist-search/backups/manual_$(date +%Y%m%d)
sudo cp /var/lib/marxist-search/articles.db /var/lib/marxist-search/backups/manual_$(date +%Y%m%d)/
sudo cp -r /var/lib/marxist-search/txtai /var/lib/marxist-search/backups/manual_$(date +%Y%m%d)/

# 3. Clean old data
sudo rm -f /var/lib/marxist-search/articles.db
sudo rm -rf /var/lib/marxist-search/txtai
sudo rm -rf /var/lib/marxist-search/cache/*

# 4. Initialize database
cd /opt/marxist-search/backend
sudo -u marxist DATA_DIR=/var/lib/marxist-search ../venv/bin/python -m src.cli.marxist_cli init-db

# 5. Archive articles (1-2 hours)
sudo -u marxist DATA_DIR=/var/lib/marxist-search ../venv/bin/python -m src.cli.marxist_cli archive run

# 6. Build index (3-5 hours)
sudo -u marxist DATA_DIR=/var/lib/marxist-search ../venv/bin/python -m src.cli.marxist_cli index build

# 7. Start services
sudo systemctl start marxist-search-api.service
sudo systemctl start marxist-search-update.timer

# 8. Check status
sudo systemctl status marxist-search-api.service
curl http://localhost:8000/api/v1/health
```

## Maintenance

### Update Backend Code

```bash
cd /opt/marxist-search/deployment/scripts
sudo ./update_backend.sh [branch_name]
```

This will:
- Pull latest changes
- Install new dependencies (if requirements.txt changed)
- Restart API service

### Update Frontend Code

```bash
cd /opt/marxist-search/deployment/scripts
sudo ./update_frontend.sh [branch_name]
```

This will:
- Pull latest changes
- Install new dependencies (if package.json changed)
- Rebuild React app
- Reload nginx

### Update Both

```bash
cd /opt/marxist-search/deployment/scripts
sudo ./update_backend.sh
sudo ./update_frontend.sh
```

### Backup Database and Index

```bash
cd /opt/marxist-search/deployment/scripts
sudo ./backup.sh
```

Backups are stored in `/var/lib/marxist-search/backups/` with 7-day retention.

### Health Check

```bash
cd /opt/marxist-search/deployment/scripts
sudo ./health_check.sh
```

### Incremental Index Update

The system automatically updates every 30 minutes via systemd timer. To manually trigger:

```bash
cd /opt/marxist-search/backend
sudo -u marxist DATA_DIR=/var/lib/marxist-search ../venv/bin/python -m src.scripts.incremental_update
```

### View Logs

```bash
# API logs
tail -f /var/log/marxist-search/api.log

# Error logs
tail -f /var/log/marxist-search/errors.log

# Ingestion logs
tail -f /var/log/marxist-search/ingestion.log

# Service logs
journalctl -u marxist-search-api.service -f
journalctl -u marxist-search-update.timer -f
```

### Restart Services

```bash
# Restart API
sudo systemctl restart marxist-search-api.service

# Restart update timer
sudo systemctl restart marxist-search-update.timer

# Restart nginx
sudo systemctl restart nginx

# Restart all
sudo systemctl restart marxist-search-api.service marxist-search-update.timer nginx
```

## Configuration

### Environment Variables (Systemd Only)

All environment variables are configured in systemd service files. **No .env file needed in production.**

Located in: `/etc/systemd/system/marxist-search-api.service`

```ini
Environment="DATA_DIR=/var/lib/marxist-search"
Environment="DATABASE_PATH=/var/lib/marxist-search/articles.db"
Environment="INDEX_PATH=/var/lib/marxist-search/txtai"
Environment="CACHE_PATH=/var/lib/marxist-search/cache"
Environment="ENVIRONMENT=production"
Environment="DEBUG=false"
```

After changing environment variables:
```bash
sudo systemctl daemon-reload
sudo systemctl restart marxist-search-api.service
```

### RSS Feeds

Edit RSS sources:
```bash
sudo -u marxist nano /opt/marxist-search/backend/config/rss_feeds.json
```

After changes, restart the update timer:
```bash
sudo systemctl restart marxist-search-update.timer
```

### Search Configuration

Edit search settings:
```bash
sudo -u marxist nano /opt/marxist-search/backend/config/search_config.py
```

After changes, restart the API:
```bash
sudo systemctl restart marxist-search-api.service
```

## Troubleshooting

### Services Won't Start

```bash
# Check service status
sudo systemctl status marxist-search-api.service

# View detailed logs
journalctl -u marxist-search-api.service -n 100

# Check if port 8000 is already in use
sudo netstat -tulpn | grep 8000

# Check permissions
ls -la /opt/marxist-search
ls -la /var/lib/marxist-search
ls -la /var/log/marxist-search
```

### Search Not Working

```bash
# Check if index exists
ls -lh /var/lib/marxist-search/txtai/

# Check database
sudo -u marxist sqlite3 /var/lib/marxist-search/articles.db "SELECT COUNT(*) FROM articles;"

# Test search directly
curl 'http://localhost:8000/api/v1/search?q=test&limit=5'

# Check search logs
tail -f /var/log/marxist-search/search.log
```

### Rebuild Failed

```bash
# Check rebuild log
tail -100 /var/log/marxist-search/rebuild.log

# Check disk space
df -h

# Check memory
free -h

# Try manual rebuild steps (see Manual Step-by-Step section)
```

### Old Directory References

If you're upgrading and see errors about `/opt/marxist-search-repo` or `/var/log/news-search`:

```bash
# Remove old directories
sudo rm -rf /opt/marxist-search-repo

# Create symlink for log compatibility (temporary)
sudo ln -s /var/log/marxist-search /var/log/news-search

# Update any remaining references in your scripts
grep -r "marxist-search-repo" /opt/marxist-search/deployment/
grep -r "news-search" /opt/marxist-search/deployment/
```

### Permission Errors

```bash
# Fix ownership
sudo chown -R marxist:marxist /opt/marxist-search
sudo chown -R marxist:marxist /var/lib/marxist-search
sudo chown -R marxist:marxist /var/log/marxist-search

# Fix permissions on scripts
sudo chmod +x /opt/marxist-search/deployment/scripts/*.sh
```

## Useful Commands Reference

```bash
# Service management
sudo systemctl start marxist-search-api.service
sudo systemctl stop marxist-search-api.service
sudo systemctl restart marxist-search-api.service
sudo systemctl status marxist-search-api.service

# View logs
journalctl -u marxist-search-api.service -f
tail -f /var/log/marxist-search/api.log

# Test API
curl http://localhost:8000/api/v1/health
curl 'http://localhost:8000/api/v1/search?q=socialism&limit=5'

# Database queries
sudo -u marxist sqlite3 /var/lib/marxist-search/articles.db
> SELECT COUNT(*) FROM articles;
> SELECT publication, COUNT(*) FROM articles GROUP BY publication;
> .quit

# Git operations (in /opt/marxist-search)
cd /opt/marxist-search
sudo -u marxist git status
sudo -u marxist git log --oneline -10
sudo -u marxist git pull origin main

# Disk usage
du -sh /var/lib/marxist-search/*
du -sh /opt/marxist-search/*
```

## Migration Checklist

Migrating from old structure to new:

- [ ] Backup existing database and index
- [ ] Note current git branch and commit
- [ ] Stop all services
- [ ] Remove old directories (`/opt/marxist-search-repo`, old `/opt/marxist-search`)
- [ ] Clone repository to `/opt/marxist-search`
- [ ] Create/update `marxist` user
- [ ] Create log directory `/var/log/marxist-search`
- [ ] Set all permissions (marxist user)
- [ ] Create venv at `/opt/marxist-search/venv`
- [ ] Install Python dependencies
- [ ] Build frontend
- [ ] Update systemd service files
- [ ] Run `rebuild_all.sh` or restore backup database/index
- [ ] Test API health endpoint
- [ ] Test search functionality
- [ ] Monitor logs for errors

## Support

For issues:
1. Check logs in `/var/log/marxist-search/`
2. Check service status: `sudo systemctl status marxist-search-api.service`
3. Review this guide's Troubleshooting section
4. Check GitHub issues: https://github.com/domwxyz/marxist-search/issues
