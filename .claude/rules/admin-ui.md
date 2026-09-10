---
paths: admin-ui/**, search_api/routers/auth.py, search_api/routers/admin_config.py
---

# Admin UI Rules

- The Admin UI is a React + Vite SPA that talks to the FastAPI backend (`search_api/`). It does not import from or depend on `bilingual_etl/` directly — provider/config changes go through the `app_config` DB table via the FastAPI admin endpoints.
- Basic auth (R26): credentials stored as bcrypt hashes in `app_config` or env. Never store plaintext passwords. Session management uses a JWT or signed cookie issued by the FastAPI `/auth/login` endpoint.
- The provider dropdown (R25) writes to `app_config` key `llm_provider` / `embedding_provider`. The ETL reads these at the start of each run — changes do not take effect mid-run.
- System prompt editing (R24) writes to `app_config` keys `prompt_translation` / `prompt_enrichment`. Include a "Reset to default" button that restores the seed values from a known-good default in the codebase.
- The Admin UI has no access to the Search API's search endpoints — it only talks to `/auth/*` and `/admin/config/*`. Don't wire the admin panel to `/search/*` or `/match/*` unless a new requirement is added.
