# Systemd Service Verification & Deployment Guide

This guide helps you verify and deploy the systemd service files correctly for the bge-base-en-v1.5 migration.

## Pre-Deployment Verification (Run in Dev/Repo)

### 1. Verify Service Files Have Correct Content

```bash
cd /home/user/marxist-search

# Check that NO trust_remote_code exists in service files
grep -i "trust_remote_code" deployment/systemd/*.service
# Expected: No output (exit code 1)

# Check that NO download_model references exist
grep -i "download_model" deployment/systemd/*.service
# Expected: No output (exit code 1)

# Check that files exist
ls -l deployment/systemd/
# Expected:
#   - marxist-search-api.service
#   - marxist-search-update.service
#   - marxist-search-update.timer
```

### 2. Review Service File Contents

```bash
# Review API service
cat deployment/systemd/marxist-search-api.service

# Review update service
cat deployment/systemd/marxist-search-update.service

# Review update timer
cat deployment/systemd/marxist-search-update.timer
```

**What to look for:**
- ✅ No `TRANSFORMERS_TRUST_REMOTE_CODE` environment variables
- ✅ Correct paths: `/opt/marxist-search`, `/var/lib/marxist-search`
- ✅ Correct user: `marxist`
- ✅ Correct Python path: `/opt/marxist-search/venv/bin/python`

## Production Deployment Steps

### 3. Copy Service Files to Production System

**Option A: If deploying to production server**
```bash
# On production server (as root or with sudo)
cd /opt/marxist-search

# Stop existing services first
sudo systemctl stop marxist-search-api.service 2>/dev/null || true
sudo systemctl stop marxist-search-update.timer 2>/dev/null || true

# Copy new service files
sudo cp deployment/systemd/marxist-search-api.service /etc/systemd/system/
sudo cp deployment/systemd/marxist-search-update.service /etc/systemd/system/
sudo cp deployment/systemd/marxist-search-update.timer /etc/systemd/system/

# Set correct permissions
sudo chmod 644 /etc/systemd/system/marxist-search-api.service
sudo chmod 644 /etc/systemd/system/marxist-search-update.service
sudo chmod 644 /etc/systemd/system/marxist-search-update.timer

# Reload systemd daemon to recognize changes
sudo systemctl daemon-reload
```

**Option B: If testing locally with systemd**
```bash
# Same commands as above, just run locally
cd /home/user/marxist-search
sudo cp deployment/systemd/*.service /etc/systemd/system/
sudo cp deployment/systemd/*.timer /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/marxist-search-*
sudo systemctl daemon-reload
```

### 4. Verify Installation

```bash
# Check files are in the right place
ls -l /etc/systemd/system/marxist-search*

# Verify content matches repo (no modifications during copy)
diff deployment/systemd/marxist-search-api.service /etc/systemd/system/marxist-search-api.service
diff deployment/systemd/marxist-search-update.service /etc/systemd/system/marxist-search-update.service
diff deployment/systemd/marxist-search-update.timer /etc/systemd/system/marxist-search-update.timer
# Expected: No output (files are identical)

# Verify systemd can parse the files
sudo systemctl status marxist-search-api.service
sudo systemctl status marxist-search-update.service
sudo systemctl status marxist-search-update.timer
# Expected: Shows "Loaded: loaded" (even if inactive)
```

### 5. Grep for Problematic Content in Installed Files

```bash
# Check installed service files for trust_remote_code
grep -i "trust_remote_code" /etc/systemd/system/marxist-search*.service
# Expected: No output

# Check for download_model references
grep -i "download_model" /etc/systemd/system/marxist-search*.service
# Expected: No output

# Verify correct environment variables are set
grep "Environment=" /etc/systemd/system/marxist-search-api.service
# Expected output should include:
#   Environment="PATH=/opt/marxist-search/venv/bin:/usr/local/bin:/usr/bin:/bin"
#   Environment="PYTHONPATH=/opt/marxist-search/backend"
#   Environment="ENVIRONMENT=production"
#   Environment="DEBUG=false"
#   Environment="DATA_DIR=/var/lib/marxist-search"
#   Environment="DATABASE_PATH=/var/lib/marxist-search/articles.db"
#   Environment="INDEX_PATH=/var/lib/marxist-search/txtai"
#   Environment="CACHE_PATH=/var/lib/marxist-search/cache"
```

### 6. Enable and Start Services

```bash
# Enable services to start on boot
sudo systemctl enable marxist-search-api.service
sudo systemctl enable marxist-search-update.timer

# Start the services
sudo systemctl start marxist-search-api.service
sudo systemctl start marxist-search-update.timer

# Verify they're running
sudo systemctl status marxist-search-api.service
sudo systemctl status marxist-search-update.timer

# Check for any errors in logs
sudo journalctl -u marxist-search-api.service -n 50
sudo journalctl -u marxist-search-update.timer -n 20
```

## Quick Verification Commands

### One-Line Verification Script

```bash
# Run this to verify everything is correct
cat << 'VERIFY_EOF' | sudo bash
echo "=== Systemd Service Verification ==="
echo ""
echo "1. Checking service files exist..."
ls -l /etc/systemd/system/marxist-search* && echo "✓ Files found" || echo "✗ Files missing"
echo ""
echo "2. Checking for trust_remote_code..."
if grep -qi "trust_remote_code" /etc/systemd/system/marxist-search*.service 2>/dev/null; then
    echo "✗ FOUND trust_remote_code - NEEDS CLEANUP"
    grep -n "trust_remote_code" /etc/systemd/system/marxist-search*.service
else
    echo "✓ No trust_remote_code found"
fi
echo ""
echo "3. Checking for download_model..."
if grep -qi "download_model" /etc/systemd/system/marxist-search*.service 2>/dev/null; then
    echo "✗ FOUND download_model - NEEDS CLEANUP"
    grep -n "download_model" /etc/systemd/system/marxist-search*.service
else
    echo "✓ No download_model found"
fi
echo ""
echo "4. Checking environment variables..."
echo "API Service Environment:"
grep "Environment=" /etc/systemd/system/marxist-search-api.service | head -10
echo ""
echo "5. Checking service status..."
systemctl is-enabled marxist-search-api.service 2>/dev/null && echo "✓ API service enabled" || echo "○ API service not enabled"
systemctl is-active marxist-search-api.service 2>/dev/null && echo "✓ API service running" || echo "○ API service not running"
systemctl is-enabled marxist-search-update.timer 2>/dev/null && echo "✓ Update timer enabled" || echo "○ Update timer not enabled"
systemctl is-active marxist-search-update.timer 2>/dev/null && echo "✓ Update timer running" || echo "○ Update timer not running"
echo ""
echo "=== Verification Complete ==="
VERIFY_EOF
```

## Troubleshooting

### If Services Won't Start

```bash
# Check for syntax errors
sudo systemd-analyze verify /etc/systemd/system/marxist-search-api.service
sudo systemd-analyze verify /etc/systemd/system/marxist-search-update.service

# Check detailed status
sudo systemctl status marxist-search-api.service -l --no-pager
sudo journalctl -u marxist-search-api.service -n 100 --no-pager

# Check if paths exist
ls -la /opt/marxist-search/venv/bin/python
ls -la /opt/marxist-search/backend/src/api/main.py
ls -la /var/lib/marxist-search/
```

### If You Need to Reinstall

```bash
# Stop and disable services
sudo systemctl stop marxist-search-api.service marxist-search-update.timer
sudo systemctl disable marxist-search-api.service marxist-search-update.timer

# Remove old files
sudo rm /etc/systemd/system/marxist-search-api.service
sudo rm /etc/systemd/system/marxist-search-update.service
sudo rm /etc/systemd/system/marxist-search-update.timer

# Reload daemon
sudo systemctl daemon-reload

# Now follow deployment steps again from step 3
```

## Production Deployment Checklist

- [ ] Git repo is at `/opt/marxist-search` on production server
- [ ] Latest code pulled from correct branch
- [ ] Service files copied to `/etc/systemd/system/`
- [ ] Files have 644 permissions
- [ ] `systemctl daemon-reload` executed
- [ ] No `trust_remote_code` in any service files
- [ ] No `download_model` references in any service files
- [ ] Environment variables point to `/var/lib/marxist-search`
- [ ] Python path is `/opt/marxist-search/venv/bin/python`
- [ ] Services enabled with `systemctl enable`
- [ ] Services started with `systemctl start`
- [ ] Health check passes: `curl http://localhost:8000/api/v1/health`
- [ ] Logs show no errors: `journalctl -u marxist-search-api.service -n 50`

## Quick Reference: File Locations

| What | Repo Location | System Location |
|------|---------------|-----------------|
| API Service | `deployment/systemd/marxist-search-api.service` | `/etc/systemd/system/marxist-search-api.service` |
| Update Service | `deployment/systemd/marxist-search-update.service` | `/etc/systemd/system/marxist-search-update.service` |
| Update Timer | `deployment/systemd/marxist-search-update.timer` | `/etc/systemd/system/marxist-search-update.timer` |
| Python venv | `venv/` | `/opt/marxist-search/venv/` |
| Backend code | `backend/` | `/opt/marxist-search/backend/` |
| Data directory | N/A | `/var/lib/marxist-search/` |
| Logs | N/A | `/var/log/marxist-search/` |

## Environment Variables Reference

The services use these environment variables (all configured in service files):

```ini
Environment="PATH=/opt/marxist-search/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=/opt/marxist-search/backend"
Environment="ENVIRONMENT=production"
Environment="DEBUG=false"
Environment="DATA_DIR=/var/lib/marxist-search"
Environment="DATABASE_PATH=/var/lib/marxist-search/articles.db"
Environment="INDEX_PATH=/var/lib/marxist-search/txtai"
Environment="CACHE_PATH=/var/lib/marxist-search/cache"
```

**Important:** No `TRANSFORMERS_TRUST_REMOTE_CODE` variable should exist!
