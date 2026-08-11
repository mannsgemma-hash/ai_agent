# Business Back-Office Agent — Architecture & Roadmap

An AI agent for the back end of the business, integrating **Xero** (accounting)
and **Etsy** (marketplace), built in **Python / FastAPI** with **Claude** as the
reasoning engine.

Status: planning only. No application code yet.

---

## 1. What the agent does

Five capabilities, in rough priority order:

1. **Expenses from Etsy → Xero.** Turn Etsy seller fees, transaction fees,
   shipping labels, ads, etc. into expense records (bills or spend-money
   transactions) in Xero.
2. **Expenses from email → Xero.** Read supplier invoices and receipts that
   arrive by email (body + PDF/image attachments), extract the vendor, amount,
   tax, and date, and create the matching expense in Xero.
3. **Sync Etsy sales → Xero.** Pull Etsy orders/receipts and record the revenue
   (and the Etsy fees netted against each payout) in Xero.
4. **Reporting & Q&A.** Answer natural-language questions — *"what were my Etsy
   fees last month?"*, *"reconcile this payout"*, *"how much VAT do I owe?"* —
   against live Xero and Etsy data.
5. **Inventory / listings operations.** Read and update Etsy listings, stock
   levels, and pricing, optionally driven by data held in Xero.

---

## 2. The core design principle

**Use Claude for judgment; use plain code for plumbing.**

The agent is *not* one big autonomous loop that "does accounting." The reliable,
well-defined work — OAuth, API calls, pagination, retries, idempotency, writing
to a database — is deterministic code. Claude is used only where a task needs
genuine language understanding or judgment:

| Task | Handled by |
|------|-----------|
| OAuth token exchange & refresh | Code |
| Fetching Etsy orders / Xero reports | Code |
| Deduplication & idempotency | Code |
| **Reading a receipt email → structured fields** | **Claude** |
| **Choosing the right Xero account / category** | **Claude** |
| **Answering natural-language questions** | **Claude** |
| Writing the transaction to Xero | Code (from Claude's structured output) |
| **Approving a financial write** | **Human** (see §6) |

This keeps money-touching operations predictable and auditable, and reserves the
LLM for the fuzzy parts it's actually good at.

---

## 3. System architecture

```
                         ┌───────────────────────────┐
   Email (Gmail)  ─────► │                           │
   Etsy webhooks/poll ─► │      FastAPI backend      │ ◄──── Chat / UI (Q&A)
                         │                           │
                         │  ┌─────────────────────┐  │
                         │  │  Agent orchestrator │  │  Claude API
                         │  │  (Claude tool loop) │◄─┼──►(Opus 5 /
                         │  └─────────┬───────────┘  │    tool use)
                         │            │              │
                         │   Tools:   │              │
                         │   • xero.*  • etsy.*       │
                         │   • email.* • db.*         │
                         └─────┬──────────────┬──────┘
                               │              │
                    ┌──────────▼───┐   ┌──────▼────────┐
                    │   Postgres   │   │ Background     │
                    │ tokens/state │   │ worker (Etsy   │
                    │ audit/queue  │   │ poll, email    │
                    └──────────────┘   │ ingest, retry) │
                                       └────────────────┘
                          │                    │
                    ┌─────▼─────┐        ┌─────▼─────┐
                    │  Xero API │        │  Etsy API │
                    │  OAuth2   │        │  OAuth2   │
                    └───────────┘        └───────────┘
```

### Components

- **FastAPI backend** — HTTP API, OAuth callback endpoints, chat/Q&A endpoint,
  Etsy webhook receiver, email webhook receiver.
- **Agent orchestrator** — a Claude tool-use loop. Claude is given a set of
  typed tools (below) and drives the multi-step work; the harness executes each
  tool call in code. The **Claude Agent SDK / Tool Runner** handles the loop.
- **Tools exposed to Claude** — thin, typed wrappers over Xero, Etsy, email, and
  the database. Financial *writes* are separate, gated tools (§6).
- **Background worker** — scheduled jobs: poll Etsy for new receipts, ingest new
  emails, run token refresh, retry failed writes. (APScheduler, Celery, or a
  simple asyncio loop — decide at build time.)
- **Postgres** — OAuth tokens (encrypted), sync cursors, an idempotency ledger,
  an audit log of every action, and a review queue for pending approvals.

### Suggested project layout

```
app/
  main.py                 # FastAPI app + routes
  config.py               # settings (env-driven)
  auth/
    xero_oauth.py         # Xero OAuth2 + token refresh
    etsy_oauth.py         # Etsy OAuth2 + token refresh
    tokens.py             # encrypted token storage
  integrations/
    xero_client.py        # Xero API wrapper
    etsy_client.py        # Etsy Open API v3 wrapper
    email_source.py       # Gmail / IMAP ingestion
  agent/
    orchestrator.py       # Claude tool-use loop
    tools.py              # tool definitions (schemas + handlers)
    prompts.py            # system prompts
    extract.py            # receipt/email → structured fields (Claude)
    categorize.py         # expense → Xero account mapping (Claude)
  flows/
    etsy_expenses.py      # Etsy fees → Xero
    etsy_sales.py         # Etsy sales → Xero
    email_expenses.py     # email receipts → Xero
    inventory.py          # Etsy listings ops
  workers/
    scheduler.py          # polling & retry jobs
  db/
    models.py             # SQLAlchemy models
    migrations/           # Alembic
  tests/
```

---

## 4. The integrations

### Xero
- **Auth:** OAuth 2.0, authorization-code flow, with refresh tokens (Xero access
  tokens last 30 min; refresh tokens rotate on use — must persist the new one).
- **API:** Accounting API — Invoices (sales), Bills / `ACCPAY` invoices and
  Spend Money bank transactions (expenses), Contacts, Accounts (chart of
  accounts), Reports.
- **SDK:** official `xero-python`.
- **Note:** every expense needs an **account code** and **tax rate** — the
  categorization step (Claude) maps to your chart of accounts.

### Etsy
- **Auth:** OAuth 2.0 (PKCE), scoped tokens, refresh tokens.
- **API:** Etsy Open API v3 — `getShopReceipts` (orders), transactions, ledger
  entries (fees/payouts), `getListingsByShop` and listing update endpoints
  (inventory/pricing).
- **Webhooks:** Etsy's push support is limited, so **polling on a schedule is
  the primary mechanism**; track a cursor so we only process new records.

### Email
- **Option A (recommended): Gmail API** with a `watch` subscription → Pub/Sub →
  webhook. Clean, structured, good attachment handling.
- **Option B: IMAP polling** — simpler to start, less real-time.
- **Option C: forward-to-address** — a dedicated inbox that forwards to a webhook.
- Claude reads the email body **plus** PDF/image attachments (the Claude API
  accepts PDFs and images directly) to extract expense fields.

---

## 5. Key flows

**Flow A — Etsy sales → Xero**
Poll `getShopReceipts` → for each new receipt, create a Xero sales invoice (or
bank transaction for the payout) → record Etsy fees as an expense against the
same payout → mark the receipt processed in the idempotency ledger.

**Flow B — Expenses from email**
Email arrives → worker fetches body + attachments → Claude extracts
`{vendor, date, total, tax, currency, line items}` → Claude suggests a Xero
account/category → a **draft** bill is created in Xero (status `DRAFT`) and added
to the review queue → human approves → code posts it as authorised.

**Flow C — Etsy fee expenses**
Read Etsy ledger/fee entries → group by type (listing, transaction, ads,
shipping label) → create the corresponding expenses in Xero.

**Flow D — Reporting & Q&A**
User asks a question → Claude, with read-only Xero/Etsy tools, gathers the data
and answers. No writes on this path.

**Flow E — Inventory / listings**
Read Etsy listings → optionally reconcile against Xero inventory data → update
stock/price via Etsy API (gated the same way as financial writes if it changes
live pricing).

---

## 6. Guardrails (the part that matters for accounting)

- **Human-in-the-loop for financial writes.** Expenses and sales are created as
  **`DRAFT`** in Xero and placed in a review queue. Nothing is authorised
  without approval (at least until you trust it on a category-by-category basis).
- **Idempotency ledger.** Every source record (Etsy receipt ID, email message
  ID) is recorded once; re-processing is a no-op. This is what stops duplicate
  bookkeeping entries.
- **Full audit log.** Every tool call, extraction, categorization, and write is
  logged with inputs, Claude's output, and the resulting Xero object ID.
- **Secrets management.** OAuth tokens encrypted at rest; API keys and client
  secrets in a secrets manager / env, never in code or the repo.
- **Confidence + escalation.** Low-confidence extractions (unreadable receipt,
  ambiguous vendor) are flagged for manual entry rather than guessed.

---

## 7. Technology choices

| Concern | Choice |
|---------|--------|
| Language / framework | Python 3.12 + FastAPI |
| Reasoning engine | Claude (Opus 5) via the `anthropic` SDK, tool use |
| Xero SDK | `xero-python` |
| Etsy | Etsy Open API v3 (direct HTTP / thin wrapper) |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Background jobs | APScheduler (start) → Celery/RQ if it grows |
| Email | Gmail API (recommended) or IMAP |
| Deployment | Container (Docker); host of your choice |

---

## 8. Roadmap

**Phase 0 — Foundations**
Repo scaffold, config, Postgres schema, OAuth for Xero *and* Etsy end-to-end
(connect, store tokens, refresh). Prove you can read from both APIs.

**Phase 1 — First working slice**
Pick **one** flow — recommended: *Etsy fees → Xero draft expenses* — and build it
end to end, including the idempotency ledger and audit log. This validates the
whole write path with human approval.

**Phase 2 — Email expenses**
Email ingestion + Claude extraction + Claude categorization + draft bills +
review queue.

**Phase 3 — Etsy sales sync**
Full receipts → Xero invoices/payouts with fee netting.

**Phase 4 — Reporting & Q&A**
Read-only agent + chat endpoint.

**Phase 5 — Inventory / listings ops.**

**Phase 6 — Hardening**
Reduce human-in-the-loop where trust is established, dashboards, alerting.

---

## 9. Open questions to settle before Phase 1

1. **Email source** — Gmail API, IMAP, or forward-to-address?
2. **Expense target in Xero** — Bills (`ACCPAY`) or Spend Money bank
   transactions? (Depends on how you currently do your books.)
3. **Chart of accounts** — which Xero accounts/tax rates should Etsy fees, ads,
   shipping, and typical supplier costs map to?
4. **Multi-currency** — do Etsy payouts and suppliers involve more than one
   currency?
5. **Where will this run** — a always-on server, a container platform, serverless?
6. **Who approves** — just you, or a team review step?
