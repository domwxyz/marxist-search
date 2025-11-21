# Filter Dropdown Fix - Production API URL Configuration

## Problem

The Source and Author filter dropdowns were not populating on the production site, while they worked correctly in local development.

## Root Cause

The issue was caused by incorrect API URL configuration in the production frontend build. When the frontend was built for production without a proper `.env.production` file, it could potentially use incorrect environment variables, causing the frontend to attempt connections to the wrong API endpoint.

In Create React App, environment variables are **baked into the build at build time**, not loaded at runtime. This means:

1. If a `.env` file exists with `REACT_APP_API_URL=http://localhost:8000/api/v1` during the build
2. That value gets permanently embedded in the JavaScript bundle
3. The production frontend tries to fetch from `localhost:8000` instead of the proxied `/api/v1` endpoint
4. This causes CORS errors and failed requests since `localhost` is not accessible from remote browsers

## Solution

Created a `.env.production` file that explicitly sets the correct API URL for production builds:

```bash
# frontend/.env.production
REACT_APP_API_URL=/api/v1
```

This ensures that:
- Production builds always use the relative URL `/api/v1`
- Nginx proxies these requests to the backend API
- No CORS issues occur (same-origin requests)
- The filter dropdowns receive data correctly

## How to Deploy the Fix

### Option 1: Full Frontend Rebuild (Recommended)

If you have access to the production server:

```bash
# SSH into your server
ssh user@yourdomain.com

# Navigate to the application directory
cd /opt/marxist-search/frontend

# Pull the latest changes (includes the new .env.production file)
sudo -u marxist git pull

# Rebuild the frontend with the correct production configuration
sudo -u marxist npm run build

# The build will now use .env.production and create a correct bundle
# Restart nginx to serve the new build
sudo systemctl restart nginx

# Test the fix
# Visit your site and check if the Source/Author dropdowns populate
```

### Option 2: Using the Update Script

If you're using the deployment scripts:

```bash
# On the production server
cd /opt/marxist-search/deployment
sudo ./scripts/update_frontend.sh
```

This script will:
1. Pull latest changes from git (including `.env.production`)
2. Rebuild the frontend with correct configuration
3. Restart services
4. Verify health

## Verification

After deploying, verify the fix works:

1. **Open your browser and visit your production site**
2. **Open browser DevTools** (F12)
3. **Go to the Network tab**
4. **Refresh the page** (Ctrl+Shift+R / Cmd+Shift+R for hard refresh)
5. **Look for requests to `/api/v1/sources` and `/api/v1/top-authors`**
   - ✅ They should show as successful (200 OK)
   - ✅ Response should contain arrays of sources/authors
6. **Check the Console tab**
   - ✅ No CORS errors
   - ✅ No "Failed to load filter options" errors
7. **Test the dropdowns**
   - ✅ Source dropdown should show available sources
   - ✅ Author dropdown should show top authors

## Technical Details

### Environment Variable Priority in Create React App

When building with `npm run build`:

1. `.env.production.local` (highest priority, git-ignored)
2. `.env.production` (our fix)
3. `.env.local` (git-ignored)
4. `.env` (lowest priority)

Our `.env.production` file ensures production builds use `/api/v1` unless explicitly overridden.

### API URL Resolution Flow

**Development** (`npm start`):
- `NODE_ENV` = `development`
- Uses `.env` or `.env.local`
- Falls back to `http://localhost:8000/api/v1`

**Production** (`npm run build`):
- `NODE_ENV` = `production`
- Uses `.env.production`
- API URL = `/api/v1` (relative)
- Nginx proxies to backend

### Nginx Proxy Configuration

The nginx configuration at `deployment/nginx.conf` handles the proxying:

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000/api/;
    # ... additional headers and settings
}
```

This means:
- Frontend request: `GET /api/v1/sources`
- Nginx proxies to: `http://127.0.0.1:8000/api/v1/sources`
- Backend handles and returns data
- Response flows back through nginx to browser

## Prevention

To prevent this issue in the future:

1. **Always build production frontend with `.env.production` present**
2. **Never copy `.env` files to production manually** - they should only exist in development
3. **Use the provided deployment scripts** which handle the build process correctly
4. **Test filter dropdowns after any frontend deployment**

## Related Files Modified

- `frontend/.env.production` (NEW) - Production environment configuration
- `frontend/.env.example` (UPDATED) - Added documentation about production config
- `FILTER_DROPDOWN_FIX.md` (NEW) - This documentation

## References

- Frontend API client: `frontend/src/utils/api.js` lines 3-7
- Filter component: `frontend/src/components/FilterPanel.jsx` lines 9-24
- Backend endpoints: `backend/src/api/routes.py` lines 126, 171
- Nginx config: `deployment/nginx.conf` line 60
