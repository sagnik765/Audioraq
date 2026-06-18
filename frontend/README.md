# Audioraq Web Client

The React client provides public discovery, episode and show pages, listener library workflows, and the creator-facing AI Studio.

## Development

```bash
cp .env.example .env
npm ci
npm run dev
```

Vite serves the application at `http://localhost:5173`. Set `VITE_BACKEND_URL` only when the API is running on a different origin; production uses same-origin `/api` routes.

## Production Build

```bash
npm run build
```

The build is written to `build/` so the existing FastAPI and Docker deployment contract remains unchanged.
