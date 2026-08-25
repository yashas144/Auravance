# Auravance Frontend

React dashboard for the Auravance demo backend.

## Run

```bash
npm install
npm run dev
```

## Backend Requirement

The Vite dev server proxies `/api/*` requests to:

`http://127.0.0.1:8000`

So the frontend uses `/api/v1` by default during local development.

If you want to bypass the proxy and point at a specific backend URL, create a `.env` file in `frontend`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

## What It Shows

- Demo asset list
- Live telemetry cards
- Trend charts
- Failure probability and RUL
- Alerts
- Root cause diagnostics
