# Deployment Directory

This directory contains all deployment-related files for the Marxist Search Engine.

## Quick Start

```bash
cd deployment
sudo ./deploy.sh yourdomain.com
```

## What's Inside

- **deploy.sh** - Automated deployment script
- **nginx.conf** - Nginx reverse proxy configuration
- **.env.production.example** - Environment variables template
- **deployment_guide.txt** - Comprehensive deployment guide (700+ lines)
- **DEPLOYMENT.md** - Quick reference and overview
- **systemd/** - Systemd service files
- **scripts/** - Utility scripts (backup, health check)

## Documentation

- Start with **DEPLOYMENT.md** for a quick overview
- Read **deployment_guide.txt** for comprehensive instructions
- All scripts include inline documentation

## Usage

### Automated Deployment

```bash
git clone https://github.com/domwxyz/marxist-search.git
cd marxist-search/deployment
sudo ./deploy.sh yourdomain.com
```

### Manual Deployment

Follow the step-by-step instructions in `deployment_guide.txt`.

### Utility Scripts

```bash
# Check system health
./scripts/health_check.sh

# Run backup
./scripts/backup.sh
```

## Files

| File | Purpose |
|------|---------|
| `deploy.sh` | One-command automated deployment |
| `nginx.conf` | Nginx configuration with rate limiting & SSL |
| `.env.production.example` | Production environment variables |
| `systemd/marxist-search-api.service` | API systemd service |
| `systemd/marxist-search-update.service` | Update service (triggered by timer) |
| `systemd/marxist-search-update.timer` | Timer for automatic updates (30 min) |
| `scripts/backup.sh` | Backup database and configuration |
| `scripts/health_check.sh` | System health monitoring |
| `deployment_guide.txt` | Complete deployment manual |
| `DEPLOYMENT.md` | Quick reference guide |

## Requirements

- Ubuntu 22.04 LTS or 24.04 LTS
- 4GB RAM minimum
- 2 vCPUs minimum
- 80GB storage
- Root/sudo access

## Support

See `deployment_guide.txt` section 8 for troubleshooting.
