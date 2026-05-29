/**
 * Shared constants for the Agri-Agent frontend.
 *
 * API_BASE is intentionally empty so all fetch() calls use relative paths
 * (e.g. `/api/analyze`). In development, Vite's proxy (vite.config.ts)
 * forwards those requests to the FastAPI backend on port 8888 — no CORS.
 * In production, configure your web server (Nginx, etc.) to proxy /api
 * and /health to the backend container.
 */
export const API_BASE = '';
