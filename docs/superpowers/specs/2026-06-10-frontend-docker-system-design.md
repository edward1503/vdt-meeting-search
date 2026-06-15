# Frontend Docker System Design

## Goal

Make `frontend/` the primary React/Vite dashboard, wire it to the FastAPI retrieval API, and run the full development system with Docker Compose on hot-reload ports.

## Architecture

The system runs four services in development: `elasticsearch`, `redis`, `api`, and `frontend`. The frontend is a Vite React app served on host port `3001`; it proxies `/api/*` to the FastAPI container. The API serves retrieval endpoints on port `8000`, uses Elasticsearch for search, and uses Redis as an optional query-result cache for repeated `/search` calls.

## Docker Design

Frontend Docker builds use multi-stage targets: `deps` installs dependencies from `package-lock.json`, `dev` runs Vite with bind-mounted source and a named `node_modules` volume for fast hot reload, `build` creates static assets, and `prod` serves the built app with Nginx. Backend Docker builds use a dependency stage and a runtime stage with Python package cache-friendly ordering.

## Latency Design

Redis is added as a low-risk cache layer for repeated retrieval requests. Cache keys include query text, method, top-k, and active Elasticsearch index. The cache has a short TTL so benchmark and index changes are not hidden for long. If Redis is unavailable or errors, the API falls back to Elasticsearch and still returns results.

## Decisions

- `frontend/` replaces the old static HTML demo as the main UI app.
- Frontend dev port is `3001`.
- Docker hot reload is enabled for both Vite and Uvicorn.
- `node_modules` is ignored by git and kept in a Docker named volume during dev.
- `.gitattributes` tracks TypeScript, JavaScript, CSS, JSON, lockfiles, and Docker-related files consistently.
