# Deployment Files

This directory contains all the necessary files and configurations for deploying the Marxist Search Engine to a production Linux VPS.

## Directory Structure

```
deployment/
├── DEPLOYMENT.md                    # This file
├── deployment_guide.txt             # Comprehensive deployment guide
├── deploy.sh                        # Automated deployment script
├── nginx.conf                       # Nginx configuration
├── .env.production.example          # Environment variables template
├── systemd/                         # Systemd service files
│   ├── marxist-search-api.service
│   ├── marxist-search-update.service
│   └── marxist-search-update.timer
└── scripts/                         # Utility scripts
    ├── backup.sh
    ├── health_check.sh
    ├── update_frontend.sh
    └── update_backend.sh
```

## Files Overview

### Configuration Files

- **nginx.conf** - Nginx reverse proxy configuration
  - Serves frontend static files
  - Proxies API requests to FastAPI backend
  - Includes rate limiting and security headers
  - Contains both HTTP and HTTPS configurations

- **.env.production.example** - Production environment variables template
  - Copy to `/opt/marxist-search/backend/.env`
  - Configure for your production environment

### Systemd Service Files

Located in `systemd/` directory:

- **marxist-search-api.service** - Main API service
  - Runs FastAPI application via Uvicorn
  - Single worker process with thread pool
  - Auto-restart on failure

- **marxist-search-update.service** - Incremental update service
  - Fetches new RSS articles
  - Updates search index
  - Triggered by timer (not enabled directly)

- **marxist-search-update.timer** - Update timer
  - Runs every 30 minutes
  - Triggers update service
  - Persistent across reboots

### Scripts

Located in `scripts/` directory:

- **backup.sh** - Backup script
  - Backs up database, configuration, and optionally index
  - Automatic cleanup of old backups
  - Can be run manually or via cron

- **health_check.sh** - Health monitoring script
  - Checks all services status
  - Monitors disk and memory usage
  - Tests API endpoints
  - Useful for monitoring and debugging

### Deployment Script

- **deploy.sh** - Automated deployment script
  - One-command deployment
  - Installs all dependencies
  - Configures services
  - Sets up SSL (optional)
  - Usage: `sudo ./deploy.sh yourdomain.com`

### Documentation

- **deployment_guide.txt** - Comprehensive deployment guide
  - Step-by-step instructions
  - Both automated and manual deployment
  - Troubleshooting section
  - Maintenance and monitoring guide
  - Security hardening instructions

## Quick Start

### Option 1: Automated Deployment (Recommended)

```bash
# On your server
git clone https://github.com/domwxyz/marxist-search.git
cd marxist-search/deployment
sudo ./deploy.sh yourdomain.com
```

### Option 2: Manual Deployment

Follow the detailed instructions in `deployment_guide.txt`.

## Deployment Checklist

- [ ] Server provisioned (4GB RAM, 2 vCPUs, Ubuntu 24.04)
- [ ] Domain configured (DNS A record pointing to server)
- [ ] Run deployment script or follow manual steps
- [ ] Configure `.env` file
- [ ] Initialize database
- [ ] Run initial archiving (1-2 hours)
- [ ] Build search index (3-5 hours)
- [ ] Configure SSL certificate
- [ ] Test application
- [ ] Set up backups

## Post-Deployment

### Directory Structure

After deployment, you'll have two key directories:

- **`/opt/marxist-search-repo`** - Git repository (for pulling updates)
- **`/opt/marxist-search`** - Production deployment (running code)

**Important:** The production directory is NOT a git repo. Updates are pulled in the repo directory and copied to production.

### Service Management

```bash
# Check status
sudo systemctl status marxist-search-api
sudo systemctl status marxist-search-update.timer

# Restart services
sudo systemctl restart marxist-search-api

# View logs
tail -f /var/log/news-search/api.log
```

### Updating Code

For small changes that don't require database/index rebuilds:

```bash
# Update frontend (logo, UI changes, etc.)
cd /opt/marxist-search-repo
sudo ./deployment/scripts/update_frontend.sh

# Update backend (API logic, no index rebuild)
cd /opt/marxist-search-repo
sudo ./deployment/scripts/update_backend.sh
```

These scripts will:
1. Pull latest changes from git
2. Copy updated files to production
3. Rebuild/restart as needed
4. Verify health

**For full rebuilds** (database/index changes), see `deployment_guide.txt`.

### Health Check

```bash
# Run health check script
cd /opt/marxist-search-repo/deployment
./scripts/health_check.sh

# Or check API directly
curl http://localhost:8000/api/v1/health
```

### Backups

```bash
# Run backup script
cd /opt/marxist-search-repo/deployment
./scripts/backup.sh

# Or set up automated backups via cron
sudo crontab -e
# Add: 0 2 * * * /opt/marxist-search-repo/deployment/scripts/backup.sh
```

## Directory Structure on Server

```
/opt/marxist-search-repo/      # Git repository (source)
├── backend/
│   ├── src/
│   ├── config/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   └── package.json
└── deployment/
    └── scripts/               # Update scripts

/opt/marxist-search/           # Production deployment (running code)
├── backend/
│   ├── src/                   # Copied from repo
│   ├── config/                # Copied from repo
│   ├── venv/                  # Python virtual environment
│   └── .env                   # Production config (NOT in git)
└── frontend/
    └── build/                 # Built React app

/var/lib/marxist-search/       # Data directory
├── articles.db
├── txtai/
└── cache/

/var/log/news-search/          # Logs
├── api.log
├── ingestion.log
├── search.log
└── errors.log

/var/backups/marxist-search/   # Backups
└── daily/
```

## Important URLs

- Frontend: `http://yourdomain.com` or `https://yourdomain.com`
- API: `http://yourdomain.com/api/`
- Health: `http://yourdomain.com/api/v1/health`
- API Docs: `http://localhost:8000/docs` (development only)

## Resource Requirements

- **CPU**: 2 vCPUs minimum (search operations are CPU-bound)
- **RAM**: 4GB minimum (txtai index ~2GB + app ~1GB + OS ~1GB)
- **Storage**: 80GB SSD (index ~2GB + database ~200MB + logs/cache)
- **Network**: Standard (low bandwidth usage except initial archiving)

## Security Notes

- API rate limiting: 100 requests/minute (configurable in nginx.conf)
- Search rate limiting: 50 requests/minute
- Firewall: Only ports 22, 80, 443 open
- SSL/TLS: Use Let's Encrypt for free certificates
- Application runs as non-root user `marxist`
- Systemd security hardening enabled

## Support

For issues or questions:

1. Check `deployment/deployment_guide.txt` troubleshooting section
2. Review application logs in `/var/log/news-search/`
3. Run `deployment/scripts/health_check.sh` to diagnose issues
4. Check GitHub repository for updates

## License

See LICENSE file in project root.
