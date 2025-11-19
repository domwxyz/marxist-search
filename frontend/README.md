# Marxist Article Search - Frontend

React frontend for searching across 16,000+ Marxist articles from revolutionary communist publications.

## Tech Stack

- **React 18** - UI framework
- **Create React App** - Build tool and development server
- **TailwindCSS 3** - Utility-first CSS framework
- **Fetch API** - HTTP client (native browser API)

## Getting Started

### Prerequisites

- Node.js 14+ and npm
- Backend API running on `http://localhost:8000` (or configure via `.env`)

### Installation

```bash
npm install
```

### Configuration

Copy `.env.example` to `.env` and configure:

```env
REACT_APP_API_URL=http://localhost:8000/api/v1
```

### Development

```bash
# Start development server (with hot reload)
npm start
```

Opens at `http://localhost:3000`

### Production

```bash
# Build for production
npm run build

# Preview production build (requires serve)
npx serve -s build
```

## Project Structure

```
src/
├── components/          # React components
│   ├── SearchBar.jsx       # Main search input
│   ├── FilterPanel.jsx     # Source/author/date filters
│   ├── ResultCard.jsx      # Individual result display
│   ├── ResultsList.jsx     # Results container
│   ├── Pagination.jsx      # Pagination controls
│   └── StatsDisplay.jsx    # Index statistics
├── hooks/              # Custom React hooks
│   ├── useSearch.js        # Search state management
│   └── useFilters.js       # Filter state management
├── utils/              # Utility functions
│   └── api.js              # API client
├── App.js              # Main app component
└── index.js            # Entry point
```

## Features

- **Semantic Search** - Natural language search with debouncing (300ms)
- **Advanced Filters** - Source, author, and date range filtering
- **Pagination** - Navigate results with configurable page size (10/25/50/100)
- **Responsive Design** - Mobile-friendly interface
- **Real-time Stats** - Index statistics display
- **Error Handling** - Graceful error messages

## API Endpoints

- `POST /api/v1/search` - Search articles
- `GET /api/v1/top-authors` - Get top authors
- `GET /api/v1/sources` - Get sources
- `GET /api/v1/stats` - Get statistics

## Deployment

The production build (`build/` folder) can be deployed to:

- Static hosting (Netlify, Vercel, GitHub Pages)
- S3 + CloudFront
- Nginx (see deployment docs)

## Troubleshooting

**API Connection Issues:**
- Verify backend is running
- Check CORS settings
- Confirm `.env` has correct API URL

**Build Errors:**
```bash
rm -rf node_modules package-lock.json
npm install
```

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers

---

Built with Create React App. See [CRA docs](https://create-react-app.dev/) for more details.
