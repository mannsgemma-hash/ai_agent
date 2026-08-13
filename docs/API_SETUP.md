# API Setup Guide

How to obtain credentials for every service the agent uses. Work through these in
order. Portal UIs change wording over time, but the OAuth flow underneath is
stable — the canonical URLs and required values below are what matter.

**Golden rules**
- Every secret goes in `.env` / a secrets manager — **never** committed to git.
- Register a **redirect URI** for each OAuth service (table at the bottom). Use a
  `localhost` URI for development and your real HTTPS domain for production.
- For each service you'll get a **client ID** and **client secret**, complete a
  one-time browser authorization, and store the resulting **refresh token**. The
  app then refreshes access tokens automatically.

---

## 0. Anthropic (the agent's brain)

1. Go to **console.anthropic.com** → sign in.
2. **Settings → API keys → Create key**. Copy it (shown once).
3. Add billing / credit.
4. Store as `ANTHROPIC_API_KEY`.

That's the only credential the reasoning engine itself needs.

---

## 1. Xero (accounting)

**Prereq:** a Xero login. For development you can use Xero's **Demo Company** so
you're not testing against live books.

1. Go to **developer.xero.com** → **My Apps** → **New app**.
2. Integration type: **Web app** (this is the auth-code flow for a backend).
3. Fill in app name, a company/website URL, and the **OAuth 2.0 redirect URI**
   (e.g. `http://localhost:8000/auth/xero/callback` for dev).
4. Save. Copy the **Client ID**, then **Generate a secret** and copy it.
5. **Scopes** you'll request during authorization:
   - `offline_access` — **required** to get a refresh token
   - `accounting.transactions` — create invoices/bills/bank transactions
   - `accounting.contacts` — vendors/customers
   - `accounting.settings` — chart of accounts, tax rates
   - `accounting.reports.read` — reporting/Q&A
   - `openid profile email`
6. **Gotchas**
   - Access tokens last **30 minutes**; refresh tokens are **rolling** — each
     refresh returns a *new* refresh token you must persist, or you lose access.
   - After authorizing, call the **`/connections`** endpoint to get the
     **tenant ID** (your organisation); every API call needs the
     `xero-tenant-id` header.

Store: `XERO_CLIENT_ID`, `XERO_CLIENT_SECRET`.

---

## 2. Etsy (marketplace)

**Prereq:** an Etsy account **with a shop** (you need a seller shop to manage
listings and read orders).

1. Go to **etsy.com/developers** → **Create a New App** (Register as a developer
   if prompted).
2. Fill in the app details. On approval you get an **API Key (keystring)** =
   your client ID, and a **shared secret**.
3. Register your **redirect URI** (e.g. `http://localhost:8000/auth/etsy/callback`).
4. **Auth:** OAuth 2.0 **with PKCE** (required by Etsy).
5. **Scopes** (space-separated at authorization):
   - `listings_r listings_w` — read/create/update listings
   - `transactions_r` — orders/receipts (for the sales sync)
   - `shops_r shops_w` — shop + inventory
   - (`billing_r` if you want fee/ledger detail)
6. **Gotchas**
   - New apps may start with **limited/personal access**; for your own shop this
     is usually fine, but note Etsy reviews apps and gates some scopes.
   - **Rate limits:** ~10 requests/second, ~10,000/day — the background poller
     must respect these.

Store: `ETSY_API_KEY` (client ID), `ETSY_SHARED_SECRET`.

---

## 3. Gmail (receipts) — via Google Cloud

This one has the most friction; read the gotchas before choosing an approach.

1. Go to **console.cloud.google.com** → **Create Project**.
2. **APIs & Services → Library →** enable **Gmail API** (and **Cloud Pub/Sub
   API** if you'll use real-time push).
3. **APIs & Services → OAuth consent screen:** choose **External**, add your
   app details, add the Gmail scope, and add **yourself as a Test user**.
4. **Credentials → Create credentials → OAuth client ID → Web application.** Add
   the redirect URI (`http://localhost:8000/auth/gmail/callback`). Copy the
   **client ID** and **client secret** (or download the JSON).
5. **Scopes**
   - `https://www.googleapis.com/auth/gmail.readonly` — read receipt emails
   - (`.../auth/gmail.modify` if you want to label/mark them processed)
6. **Real-time (optional):** create a **Pub/Sub topic**, grant Gmail permission
   to publish to it, then call **`users.watch`** to subscribe. Renew the watch
   before it expires (~7 days). Simpler start: **poll** the inbox on a schedule.

**⚠️ The big Gmail decision — pick one:**

- **A) Personal Gmail in "Testing" mode (simplest to start).** Gmail scopes are
  *restricted*; publishing the app for many users requires Google verification
  (and a security assessment). But for a **single internal user** you can leave
  the app in **Testing** mode with yourself as a test user and skip verification
  — the catch is **refresh tokens expire every 7 days** in Testing mode, so the
  app must re-authorize weekly. Fine for early dev, annoying for production.
- **B) Google Workspace + service account + domain-wide delegation
  (recommended for a business).** If the business email is on **Google
  Workspace**, create a **service account**, enable **domain-wide delegation**,
  and authorize the Gmail scope in the Admin console. The app then impersonates
  the mailbox with **no per-user consent screen and no 7-day expiry**. This is
  the robust production setup.

Store: `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` (or the service-account JSON).

---

## 4. Dropbox (file storage)

1. Go to **dropbox.com/developers/apps** → **Create app**.
2. Choose **Scoped access**.
3. Access type: **App folder** *(recommended — the app only sees its own folder,
   least privilege)*, or **Full Dropbox** if assets live elsewhere.
4. Name the app and create it. Copy the **App key** and **App secret**.
5. **Permissions** tab — enable the scopes, then **Submit**:
   - `files.metadata.read`, `files.content.read`
   - (`files.content.write` only if archiving receipts back to Dropbox)
6. **Settings** tab — add the OAuth **redirect URI**
   (`http://localhost:8000/auth/dropbox/callback`).
7. **Gotcha:** Dropbox access tokens are short-lived (~4h). Request offline
   access (`token_access_type=offline`) during authorization to get a **refresh
   token**.

Store: `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`.

---

## 5. Canva (thumbnails) — via the Canva MCP server

Because we're **not** on Canva Enterprise, the integration path is Canva's
**official MCP server**, not a self-built API client. There are (almost) no
credentials for *you* to manage — you authorize in the browser.

1. In your AI client (**Claude Desktop / Claude Code**, or whatever will host the
   chat face), open the **MCP servers / connectors** settings.
2. **Add the Canva MCP server** (follow Canva's MCP setup page — it provides the
   server URL / install command).
3. The first time the agent uses it, Canva opens a **browser OAuth prompt** — log
   in and approve. Tokens are managed by the MCP client, not your code.
4. **What you get without Enterprise:** design/export tools and Canva's **AI
   "generate a design from a prompt"** (Magic Design) — enough to produce
   thumbnails. **Autofill / Brand Templates remain Enterprise-only.**
5. For **headless/volume** thumbnail generation (no agent in the loop), use the
   **Pillow-on-a-Canva-template** backend instead — no Canva credentials needed
   at all (see `PLAN.md` §4).

*(Building your own Canva Connect API client — developer.canva.com, client
ID/secret, scopes — is only worth it if you later go Enterprise for Autofill.)*

---

## Redirect URIs (register these per service)

| Service | Dev redirect URI | Prod redirect URI |
|---------|------------------|-------------------|
| Xero    | `http://localhost:8000/auth/xero/callback`    | `https://<domain>/auth/xero/callback` |
| Etsy    | `http://localhost:8000/auth/etsy/callback`    | `https://<domain>/auth/etsy/callback` |
| Gmail   | `http://localhost:8000/auth/gmail/callback`   | `https://<domain>/auth/gmail/callback` |
| Dropbox | `http://localhost:8000/auth/dropbox/callback` | `https://<domain>/auth/dropbox/callback` |
| Canva   | *handled by the MCP client (browser OAuth)*   | *same* |

---

## `.env` template

```dotenv
# Anthropic
ANTHROPIC_API_KEY=

# Xero
XERO_CLIENT_ID=
XERO_CLIENT_SECRET=
XERO_REDIRECT_URI=http://localhost:8000/auth/xero/callback

# Etsy
ETSY_API_KEY=
ETSY_SHARED_SECRET=
ETSY_REDIRECT_URI=http://localhost:8000/auth/etsy/callback

# Gmail (option A: OAuth client)   (option B: point to service-account JSON)
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REDIRECT_URI=http://localhost:8000/auth/gmail/callback
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Dropbox
DROPBOX_APP_KEY=
DROPBOX_APP_SECRET=
DROPBOX_REDIRECT_URI=http://localhost:8000/auth/dropbox/callback

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/agent

# Encryption key for stored OAuth tokens (generate a strong random value)
TOKEN_ENCRYPTION_KEY=
```

`.env` must be listed in `.gitignore`.

---

## Order of operations & effort

1. **Anthropic** (2 min) — needed for any agent work.
2. **Dropbox** (10 min) — easiest OAuth; good first end-to-end test.
3. **Xero** (15 min) — mind the tenant ID + rolling refresh token.
4. **Etsy** (15–30 min) — allow for app review.
5. **Gmail** (30–60 min) — the consent-screen/verification decision is the
   time sink; decide personal-testing vs Workspace service account up front.
6. **Canva MCP** (10 min) — just authorize in the client when we build the chat face.

Do **not** hand-code any of these OAuth flows yet — Phase 0 of the build wires
them up with a consistent auth module. This guide is so you can create the apps
and have the client IDs/secrets ready.
