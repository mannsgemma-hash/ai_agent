# Business Back-Office Agent — Architecture & Roadmap

An AI agent for the back end of the business, integrating **Xero** (accounting),
**Etsy** (marketplace), **Gmail** (receipts), and **Dropbox** (file storage),
built in **Python / FastAPI** with **Claude** as the reasoning engine.

Status: planning only. No application code yet.

---

## 1. What the agent does

1. **Create Etsy listings** from images/files held in **Dropbox** (see §5, Flow E).
2. **Record Etsy purchases as sales in Xero.** Every Etsy order becomes a sales
   invoice in Xero, with Etsy fees recorded against the payout.
3. **Expenses from Etsy → Xero.** Etsy seller/transaction/ads/shipping fees
   become expense records in Xero.
4. **Expenses from email → Xero.** Supplier invoices/receipts arriving in
   **Gmail** (body + PDF/image attachments) are extracted and posted to Xero.
5. **Reporting & Q&A.** Natural-language questions against live Xero/Etsy data.
6. **Inventory / listings operations.** Read/update Etsy listings, stock, pricing.

---

## 2. The core design principle

**Use Claude for judgment; use plain code for plumbing.**

The reliable, well-defined work — OAuth, API calls, pagination, retries,
idempotency, database writes — is deterministic code. Claude is used only where a
task needs language understanding or judgment.

| Task | Handled by |
|------|-----------|
| OAuth token exchange & refresh (Xero, Etsy, Gmail, Dropbox) | Code |
| Fetching orders / reports / files | Code |
| Deduplication & idempotency | Code |
| **Reading a receipt email → structured fields** | **Claude** |
| **Choosing the right Xero account / category** | **Claude** |
| **Drafting listing title/description/tags from an image** | **Claude** |
| **Answering natural-language questions** | **Claude** |
| Writing to Xero / creating the Etsy listing | Code (from Claude's structured output) |
| **Approving a financial write or a live listing** | **Human** (§6) |

Money-touching and publish-to-store operations stay predictable and auditable;
the LLM handles the fuzzy parts it's good at.

---

## 3. System architecture

There is **one core service** (business logic + tools + DB) with **two faces**:
an automated/event-driven face (background workers) and a conversational face
(chat). Both call the same underlying tool layer — built once.

```
        AUTOMATED FACE                          CONVERSATIONAL FACE
  ┌───────────────────────┐              ┌──────────────────────────────┐
  │ Background worker      │              │ Claude app (Desktop / web)    │
  │ • Gmail ingest         │              │      ▲  chat                  │
  │ • Etsy sales/fee sync   │             │      │  (MCP)                 │
  │ • token refresh, retry  │             │  ┌───┴──────────┐             │
  └──────────┬─────────────┘             │  │  MCP server   │  ← optional │
             │                            │  └───┬──────────┘             │
             │                            └──────┼───────────────────────┘
             ▼                                   ▼
      ┌──────────────────────────────────────────────────────┐
      │                CORE SERVICE (FastAPI)                 │
      │   Tool layer:  xero.*  etsy.*  gmail.*  dropbox.*      │
      │   Business flows + Claude extraction/categorization   │
      └───────────────┬───────────────────────┬──────────────┘
                      │                        │
             ┌────────▼────────┐      ┌────────▼─────────┐
             │    Postgres     │      │   Claude API     │
             │ tokens / state  │      │  (Opus 5, tools) │
             │ audit / queue   │      └──────────────────┘
             └─────────────────┘
                      │
   ┌───────────┬──────┴──────┬───────────┬──────────────┐
   ▼           ▼             ▼           ▼              ▼
 Xero API    Etsy API     Gmail API   Dropbox API   (chart of accounts,
 OAuth2      OAuth2       OAuth2      OAuth2          fee mappings)
```

### The tool layer (shared)

Every integration is a thin, typed wrapper. These same tools are called by the
background workers (automated flows) **and** exposed to the chat face via MCP.
Write once, use from both.

### One agent, both domains

**A single agent handles both the financial side and Etsy listing/store
management.** The agent is one Claude reasoning loop that routes a request to
whichever tool fits — Xero sales, Etsy fees, or a Dropbox→Etsy listing — so it
doesn't need to be split by domain. Most of the work is deterministic code in the
shared tool layer anyway, and the guardrails (draft + human approval) are
per-action, not per-agent, so finance stays safe alongside store management.

Split into a **coordinator + specialists** (a finance specialist and a
listings/store specialist behind one entry point) only if the combined tool set
grows confusing or you want the finance side more tightly isolated. Start with
one agent; treat the split as a later optimization.

### Suggested project layout

```
app/
  main.py
  config.py
  auth/            xero_oauth.py  etsy_oauth.py  gmail_oauth.py  dropbox_oauth.py  tokens.py
  integrations/    xero_client.py  etsy_client.py  gmail_source.py  dropbox_client.py
  agent/           orchestrator.py  tools.py  prompts.py  extract.py  categorize.py  listing_draft.py
  flows/           etsy_sales.py  etsy_expenses.py  email_expenses.py  listings.py
  mcp/             server.py        # exposes the tool layer to the Claude app (optional face)
  workers/         scheduler.py
  db/              models.py  migrations/
  tests/
```

---

## 4. The integrations

### Xero
- **Auth:** OAuth 2.0 auth-code flow; access tokens ~30 min, rotating refresh
  tokens (must persist the new refresh token on each use).
- **API:** Invoices (sales), Bills/Spend-Money (expenses), Contacts, Accounts
  (chart of accounts), Reports. SDK: `xero-python`.

### Etsy
- **Auth:** OAuth 2.0 (PKCE), scoped refresh tokens.
- **API:** Etsy Open API v3.
  - *Read sales/fees:* `getShopReceipts`, transactions, ledger entries.
  - *Create listings:* `createDraftListing` → `uploadListingImage` (up to 10) →
    `uploadListingVideo` (optional) → `updateListingInventory` (SKU, price,
    quantity, variations) → publish by updating listing `state` to `active`.
  - *Manage:* `getListingsByShop`, listing update endpoints (stock, pricing).
- **Webhooks are limited** → poll on a schedule with a stored cursor.

### Gmail
- **Auth:** OAuth 2.0.
- **Mechanism:** Gmail API with a `watch` subscription → Pub/Sub → webhook (near
  real-time). Fetch message body + attachments; Claude reads the PDF/image
  attachments directly (the Claude API accepts them).

### Dropbox
- **Auth:** OAuth 2.0 (short-lived tokens + refresh).
- **Role:** the file store for everything to be uploaded — **listing photos and
  video** (input to the Etsy listing flow), and optionally an archive of
  processed receipts.
- **API:** `files/list_folder`, `files/download`, `files/get_temporary_link`.
  A convention like `/listings/<sku>/` lets the agent find the assets for a listing.

### Canva — thumbnail generation (no Enterprise plan)
- **Role:** generate branded Etsy **thumbnails**, keeping Canva's design tools.
- **The Enterprise gate is only on Autofill / Brand Template** (hands-off
  data-merge). The other paths below need no Enterprise plan.
- **Backends behind one interface `make_thumbnail(photo, title, price) -> image`:**
  1. **Local Pillow, Canva-designed template** *(recommended default).* Design
     the template once in Canva; export the frame/overlay; the agent composites
     each product photo + text onto it automatically with **Pillow**. Free,
     per-listing, fully automated. Keeps the Canva look.
  2. **Canva Pro "Bulk Create"** *(Pro, not Enterprise).* Agent produces the data
     spreadsheet (photo links + Claude-drafted title/price); you run Bulk Create
     once in Canva; export the batch. Canva does the render; agent does the prep.
  3. **Canva Connect API without autofill.** Non-Enterprise still exposes **asset
     upload**, **create design**, and **export**. Agent uploads the photo, opens
     a design, hands you a deep edit link; you finish in Canva; agent exports the
     PNG and sends it to Etsy. Most Canva-native; one manual step per listing.
     *(Verify the asset/design/export scopes at setup — docs weren't reachable to
     re-confirm, but these have sat outside the Enterprise gate.)*
- Flow E is backend-agnostic, so we can start with #1 and switch anytime.
- **Canva MCP server (integration method, not a 4th backend).** Canva ships an
  official **MCP server** the agent connects to natively — no custom Canva client
  to build. It surfaces Canva's **AI "generate a design from a prompt"** (Magic
  Design), which is **free/Pro, not Enterprise** — a non-Enterprise way to
  produce thumbnails through Canva. Caveats: MCP is a wrapper over Canva's API
  under *your* plan, so **Autofill stays Enterprise-gated through MCP too**; and
  it's built for an agent-in-the-loop, so it suits **chat-driven** listing
  creation (§7), not silent batch automation. Verify its exact tool list / auth
  at setup (docs not reachable from here).
- **Net thumbnail strategy:** Canva **MCP** for chat-driven, in-the-loop listing
  creation; **Pillow template** (#1) for headless/volume automation.

---

## 5. Key flows

**Flow A — Etsy purchases → Xero sales**
Poll `getShopReceipts` → for each new receipt create a Xero **sales invoice** →
record Etsy fees against the payout → mark the receipt processed in the
idempotency ledger.

**Flow B — Expenses from Gmail**
Gmail `watch` fires → fetch body + attachments → Claude extracts
`{vendor, date, total, tax, currency, line items}` → Claude suggests a Xero
account → a **draft** bill is created in Xero and queued for review → human
approves → code authorises it. (Optionally archive the receipt to Dropbox.)

**Flow C — Etsy fee expenses**
Read Etsy ledger/fee entries → group by type (listing, transaction, ads,
shipping label) → create the matching Xero expenses.

**Flow D — Reporting & Q&A**
User asks a question (via the chat face, §7) → Claude gathers data with
read-only tools and answers. No writes.

**Flow E — Create an Etsy listing from Dropbox**
Trigger (chat command or a new folder in Dropbox) → agent lists the images in the
Dropbox folder → Claude drafts title, description, tags, materials, and suggested
category/attributes from the images + any notes → **generate the thumbnail** via
`make_thumbnail(photo, title, price)` (Canva Autofill or local Pillow — see §4) →
agent creates a **draft** Etsy listing, uploads the photos/video, sets inventory
(SKU, price, quantity, variations) → human reviews the draft → **publish** on
approval.
*Mirrors Etsy's own create-a-listing steps: photos/video → title →
about/category/attributes → description → inventory (price, quantity, SKU,
variations) → shipping profile → tags → publish.*

**Flow F — Inventory / listings ops**
Read Etsy listings, reconcile against Xero data where relevant, update
stock/price (price changes gated like any live-store write).

---

## 6. Guardrails

- **Human-in-the-loop for writes.** Xero expenses/sales are created as `DRAFT`;
  Etsy listings are created as **draft** and only published on approval. Nothing
  hits your books or your storefront unreviewed (relaxed per-category once trusted).
- **Idempotency ledger.** Each source record (Etsy receipt ID, Gmail message ID,
  Dropbox folder) is processed once — this is what prevents duplicate entries.
- **Full audit log** of every tool call, extraction, and resulting object ID.
- **Secrets** encrypted at rest / in a secrets manager; never in code or the repo.
- **Confidence + escalation** — low-confidence extractions/listings are flagged
  for manual handling rather than guessed.

---

## 7. Front end / interface — answering "can I use Claude's chat as the front?"

**Yes, and for an internal back-office tool it's the recommended approach.** The
pattern you read about is **MCP (Model Context Protocol)**: you build a small MCP
server that exposes your tool layer, and the **Claude app (Desktop or claude.ai
via a custom connector) becomes the chat front end** — you type
*"create a listing for the mugs in Dropbox"* or *"what were my Etsy fees last
month?"* and Claude calls your tools. No custom chat UI to build.

Three options, and it's not either/or:

| Option | What it is | Best for | Effort |
|--------|-----------|----------|--------|
| **A. MCP + Claude app** *(recommended)* | Expose tools via MCP; chat in Claude Desktop/web | Internal ops & Q&A — you/your team | Low |
| **B. Custom chat endpoint** | Your own UI + Claude API tool loop | Branded / customer-facing / embedded | High |
| **C. Managed Agents** | Anthropic hosts the loop + sandbox on a schedule | Autonomous scheduled runs | Medium |

**Connectors:** with Option A, the Claude app can load several MCP servers at
once — **our** MCP server (Xero/Etsy/Gmail/Dropbox) plus **Canva's official MCP
server** for design/thumbnail generation. The agent drives all of them in one
conversation.

**Key point:** the chat face is **optional and additive**. The automated flows
(Gmail ingest, Etsy sales/fee sync) run headless as background workers and need
no chat at all — they're triggered by events and schedules. The chat face is for
the *human-driven* actions: creating listings, approving drafts, and asking
questions. Because both faces call the same tool layer, adding MCP later is
cheap — so we can build the core + workers first and bolt on the chat face when
you want it.

Recommendation: **build the core service + workers first, then add the MCP
server (Option A)** as the conversational face. Revisit Option B only if you ever
want a branded/customer-facing chat.

---

## 8. Technology choices

| Concern | Choice |
|---------|--------|
| Language / framework | Python 3.12 + FastAPI |
| Reasoning engine | Claude (Opus 5) via the `anthropic` SDK, tool use |
| Chat front end | MCP server + Claude Desktop/web (Option A) |
| Xero | `xero-python` |
| Etsy | Etsy Open API v3 |
| Gmail | Gmail API (`watch` + Pub/Sub) |
| Dropbox | Dropbox Python SDK |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Background jobs | APScheduler (start) → Celery/RQ if it grows |
| Deployment | Container (Docker); host of your choice |

---

## 9. Roadmap

**Phase 0 — Foundations.** Repo scaffold, config, Postgres schema, OAuth for all
four services (Xero, Etsy, Gmail, Dropbox) end to end. Prove reads from each.

**Phase 1 — First working slice.** *Etsy fees → Xero draft expenses*, with the
idempotency ledger and audit log — validates the whole write path with approval.

**Phase 2 — Etsy purchases → Xero sales** (Flow A).

**Phase 3 — Gmail expenses** (Flow B): ingest + Claude extraction + drafts + review.

**Phase 4 — Create listings from Dropbox** (Flow E): Dropbox read + Claude drafting
+ draft Etsy listing + publish-on-approval.

**Phase 5 — Chat face.** MCP server over the tool layer → Q&A + human-driven ops
in the Claude app.

**Phase 6 — Inventory ops + hardening.** Reduce human-in-the-loop where trusted;
dashboards, alerting.

---

## 10. Open questions to settle before building

1. **Xero expense target** — Bills (`ACCPAY`) or Spend-Money bank transactions?
2. **Chart of accounts** — which Xero accounts/tax rates for Etsy fees, ads,
   shipping, and typical supplier costs; which account/tax rate for Etsy sales.
3. **Multi-currency** — do Etsy payouts / suppliers involve more than one currency?
4. **Dropbox layout** — folder convention that maps assets to a listing (e.g.
   `/listings/<sku>/photos`), and what metadata (price, variations) travels with them.
5. **Listing defaults** — shipping profile(s), return policy, processing time,
   shop section — set once and reused, or chosen per listing?
5a. **Canva plan** — are you on Canva Enterprise (needed for the Autofill/Brand
   Template API)? If not, thumbnails use the local Pillow backend instead.
6. **Where it runs** — always-on server, container platform, or serverless?
7. **Who approves** drafts — just you, or a team review step?
