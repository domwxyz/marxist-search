# Marxist Search - Frontend

React frontend for the Marxist Search semantic search engine. Provides a modern, responsive interface for searching across 16,000+ Marxist articles.

## Technology Stack

- **React 19** - UI framework
- **Create React App** - Build toolchain and development server
- **TailwindCSS 3** - Utility-first CSS framework
- **Fetch API** - HTTP client (native browser API)

## Features

- **Semantic Search**: Natural language search with 300ms debouncing
- **Request Cancellation**: Automatic cancellation of stale requests when new search initiated
- **Advanced Filters**: Filter by source, author, and date range
- **Date Range Presets**: Quick filters (past week, month, year, decade) plus custom date picker
- **Pagination**: Navigate results with page controls
- **Results Per Page**: Configurable page size (10, 25, 50, 100)
- **Statistics Dashboard**: Real-time index statistics
- **Responsive Design**: Mobile-friendly interface with Tailwind CSS
- **Error Handling**: User-friendly error messages
- **Loading States**: Visual feedback during searches

## Project Structure

```
frontend/
├── public/
│   ├── index.html              # HTML template
│   ├── favicon.ico             # Favicon
│   ├── android-chrome-192x192.png  # App logo (192x192)
│   ├── android-chrome-512x512.png  # App logo (512x512)
│   ├── apple-touch-icon.png    # Apple touch icon
│   ├── favicon-16x16.png       # Favicon 16x16
│   ├── favicon-32x32.png       # Favicon 32x32
│   ├── manifest.json           # PWA manifest
│   ├── site.webmanifest        # Alternative manifest
│   └── robots.txt              # Robots.txt
├── src/
│   ├── components/             # React components
│   │   ├── SearchBar.jsx          # Search input with submit button
│   │   ├── FilterPanel.jsx        # Source, author, date filters
│   │   ├── ResultsList.jsx        # Results container
│   │   ├── ResultCard.jsx         # Individual result card
│   │   ├── Pagination.jsx         # Pagination controls
│   │   ├── ResultsPerPageSelector.jsx  # Page size dropdown
│   │   └── StatsDisplay.jsx       # Index statistics
│   ├── hooks/                  # Custom React hooks
│   │   ├── useSearch.js           # Search state and logic
│   │   └── useFilters.js          # Filter state management
│   ├── utils/                  # Utilities
│   │   └── api.js                 # API client functions
│   ├── App.js                  # Main app component
│   ├── App.test.js             # App tests
│   ├── index.js                # Entry point
│   ├── index.css               # Global styles (Tailwind imports)
│   ├── setupTests.js           # Test setup
│   └── reportWebVitals.js      # Performance monitoring
├── .env.example                # Environment variables template
├── .env.production             # Production environment variables
├── tailwind.config.js          # TailwindCSS configuration
├── postcss.config.js           # PostCSS configuration
├── package.json
└── README.md
```

## Installation

### Prerequisites

- Node.js 14+ and npm
- Backend API running (default: `http://localhost:8000`)

### Setup

```bash
cd frontend
npm install
```

### Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` to configure API URL:

```env
REACT_APP_API_URL=http://localhost:8000/api/v1
```

## Development

### Start Development Server

```bash
npm start
```

Opens at `http://localhost:3000` with hot reload enabled.

### Other Commands

```bash
# Run tests
npm test

# Build for production
npm run build

# Eject from Create React App (irreversible)
npm run eject
```

## Production Build

### Build

```bash
npm run build
```

Creates optimized production build in `build/` directory with:
- Minified JavaScript and CSS
- Hashed filenames for cache busting
- Optimized bundle sizes
- Source maps for debugging

### Preview Production Build

```bash
# Install serve (if not already installed)
npm install -g serve

# Serve production build
npx serve -s build
```

Opens at `http://localhost:3000` (or next available port).

## Component Overview

### App.js
Main application component that:
- Orchestrates search and filter state
- Manages API calls via `useSearch` hook
- Handles pagination
- Renders all child components

### SearchBar.jsx
Search input with:
- Controlled input field
- Submit button
- Enter key support
- Debouncing (300ms)

### FilterPanel.jsx
Advanced filters with:
- **Source filter**: Dropdown populated from API
- **Author filter**: Dropdown with top authors from API
- **Date range filter**: Preset options (past week, past month, past 3 months, past year, 1990s, 2000s, 2010s, 2020s) plus custom date picker
- Clear filters button

### ResultsList.jsx
Results display with:
- Loading state indicator
- Error message display
- Empty state handling
- Grid of result cards

### ResultCard.jsx
Individual result card showing:
- Article title (clickable link)
- Excerpt from content
- Source and author
- Published date
- Tags (if available)
- Relevance score

### Pagination.jsx
Pagination controls with:
- Previous/Next buttons
- Page number display
- Disabled states for boundary pages

### ResultsPerPageSelector.jsx
Dropdown for results per page:
- Options: 10, 25, 50, 100
- Resets to page 1 on change

### StatsDisplay.jsx
Statistics dashboard showing:
- Total articles indexed
- Number of sources
- Date range (earliest to latest article)
- Fetched from `/api/v1/stats` endpoint

## Custom Hooks

### useSearch.js
Manages search state and API calls:
- Debounced search execution (300ms)
- Request cancellation with AbortController
- Loading and error states
- Results and pagination state
- Filter application

### useFilters.js
Manages filter state:
- Source, author, date range filters
- Custom date range (start/end dates)
- Clear all filters function
- Filter state persistence

## API Integration

The frontend communicates with the backend via `utils/api.js`:

### API Functions

```javascript
// Search articles
search(query, filters)

// Get top authors
getTopAuthors()

// Get all sources
getSources()

// Get index statistics
getStats()

// Health check
healthCheck()
```

### API Client Configuration

```javascript
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';
```

## Styling

### TailwindCSS

The project uses Tailwind CSS utility classes for styling:

```javascript
// Example from ResultCard.jsx
<div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-shadow">
  <h3 className="text-xl font-semibold text-gray-900 mb-2">
    {title}
  </h3>
</div>
```

### Custom Styles

Custom styles are defined in:
- `src/index.css` - Global styles and Tailwind imports (all styling uses Tailwind utility classes)

## Deployment

The production build can be deployed to:

### Static Hosting

- **Netlify**: Drag-and-drop `build/` folder or connect Git repo
- **Vercel**: Connect Git repo with automatic deployments
- **GitHub Pages**: Use `gh-pages` package
- **AWS S3 + CloudFront**: Upload `build/` folder

### Nginx

Serve `build/` folder with Nginx configuration:

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    root /path/to/build;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Docker

```dockerfile
FROM node:18 AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## Environment Variables

### Development (.env or .env.local)

For local development:

```env
# Backend API URL
REACT_APP_API_URL=http://localhost:8000/api/v1

# Optional: Enable debug mode
REACT_APP_DEBUG=false
```

### Production (.env.production)

**IMPORTANT**: The repository includes a `.env.production` file that automatically configures the production build:

```env
# Use relative URL so nginx can proxy /api/* to the backend
REACT_APP_API_URL=/api/v1
```

This ensures:
- ✅ No CORS issues (same-origin requests)
- ✅ Works with nginx proxy configuration
- ✅ No need to change API URL when deploying

**DO NOT** override this in production unless you have a specific reason!

### Environment File Priority

When running `npm run build`, Create React App loads files in this order:
1. `.env.production.local` (git-ignored, highest priority)
2. `.env.production` (included in repo, recommended)
3. `.env.local` (git-ignored)
4. `.env` (lowest priority)

### Common Issue: Filter Dropdowns Not Populating

If the Source and Author filter dropdowns are empty in production, this is usually caused by incorrect API URL configuration during the build.

**Fix**: Ensure `.env.production` exists and is correctly configured, then rebuild:

```bash
cd /opt/marxist-search/frontend
sudo -u marxist npm run build
```

See `FILTER_DROPDOWN_FIX.md` in the repository root for detailed troubleshooting.

## Browser Support

Supports modern browsers:

- **Chrome/Edge**: Latest 2 versions
- **Firefox**: Latest 2 versions
- **Safari**: Latest 2 versions
- **Mobile browsers**: iOS Safari, Chrome Mobile

## Troubleshooting

### API Connection Issues

**Problem**: Frontend can't connect to backend

**Solutions**:
1. Verify backend is running at `http://localhost:8000`
2. Check `.env` has correct `REACT_APP_API_URL`
3. Verify CORS is enabled in backend (`src/api/main.py`)
4. Check browser console for network errors

### CORS Errors

**Problem**: `Access-Control-Allow-Origin` errors in console

**Solution**: Ensure backend has CORS middleware configured:

```python
# backend/src/api/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Build Errors

**Problem**: `npm run build` fails

**Solutions**:
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear Create React App cache
rm -rf node_modules/.cache
npm run build
```

### Environment Variables Not Working

**Problem**: `process.env.REACT_APP_API_URL` is undefined

**Solutions**:
1. Ensure variable starts with `REACT_APP_`
2. Restart development server after changing `.env`
3. Check `.env` file is in `frontend/` directory (not `frontend/src/`)

### Slow Search Performance

**Problem**: Search feels laggy or unresponsive

**Solutions**:
1. Check debounce timeout in `useSearch.js` (default 300ms)
2. Verify backend is responding quickly
3. Check browser network tab for slow API calls

## Development Tips

### Hot Reload

Changes to source files automatically reload the browser. If hot reload stops working:

```bash
# Restart development server
Ctrl+C
npm start
```

### Debugging

Use React Developer Tools browser extension:
- Inspect component state and props
- Profile component renders
- Debug hooks

### State Management

The app uses React hooks for state management:
- `useState` for local state
- `useEffect` for side effects
- `useCallback` for memoized callbacks
- Custom hooks (`useSearch`, `useFilters`) for shared logic

## License

See LICENSE file in repository root.

## Learn More

- [Create React App Documentation](https://create-react-app.dev/)
- [React Documentation](https://react.dev/)
- [TailwindCSS Documentation](https://tailwindcss.com/docs)
