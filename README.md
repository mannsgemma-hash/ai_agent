# Back-Office Agent

An AI agent for the back end of the business, integrating **Xero**, **Etsy**,
**Gmail**, **Dropbox**, and **Canva** (via MCP), with **Claude** as the reasoning
engine.

- Architecture & roadmap: [`docs/PLAN.md`](docs/PLAN.md)
- API credential setup: [`docs/API_SETUP.md`](docs/API_SETUP.md)

## Status — Phase 0 (foundation)

In place: FastAPI app, config, database models, and a unified OAuth flow for the
four self-hosted integrations (Xero, Etsy, Gmail, Dropbox). No business logic yet.

## Run it locally

```bash
# 1. Create a virtualenv and install deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Generate an encryption key for stored tokens and paste it into .env:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Then fill in the client IDs/secrets you created (see docs/API_SETUP.md).

# 3. Start the app (defaults to SQLite — no database setup needed)
uvicorn app.main:app --reload --port 8000
```

Then:

- `GET http://localhost:8000/health` → `{"status": "ok"}`
- `GET http://localhost:8000/` → which providers are connected + connect links
- Visit `http://localhost:8000/auth/xero/login` (or `/etsy`, `/gmail`,
  `/dropbox`) to run each OAuth flow. On success the encrypted tokens are stored
  and the provider shows up as connected.

## Notes

- Tokens are encrypted at rest with `TOKEN_ENCRYPTION_KEY` (Fernet).
- Xero's tenant id is fetched and stored automatically after authorization.
- `.env` is gitignored — never commit real secrets.
- Canva uses its MCP server (no credentials here) — set up when the chat face is
  built. See `docs/PLAN.md` §4/§7.
