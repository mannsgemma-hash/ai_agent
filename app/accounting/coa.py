"""Chart of accounts mapping — Paper&Petals (Xero, AU/GST).

Source: docs/chart_of_accounts.md (exported 13 Aug 2026).

SCOPE — read this before adding anything Etsy-financial here.
------------------------------------------------------------
Etsy income and Etsy fees are ALREADY posted to Xero by the existing
Etsy<->Xero integration (that is what the ET-* accounts are for). The agent
must NOT create Etsy sales or Etsy fee transactions: doing so would
double-count. The agent's Etsy role is listings / store management only.

The agent posts:
  * INCOME    - RevenueCat app subscriptions only -> 200 Sales
  * EXPENSES  - supplier receipts captured from Gmail -> mapped below
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Income -------------------------------------------------------------

# Per instruction: all income the agent books goes to 200 Sales.
INCOME_ACCOUNT = "200"
INCOME_TAX_RATE = "OUTPUT"  # Xero AU TaxType for "GST on Income"

# Apple/Google keep a commission and remit net. The commission is an expense,
# booked separately from the gross sale (see PLAN.md Flow A).
PLATFORM_COMMISSION_ACCOUNT = "429"  # General Expenses
PLATFORM_COMMISSION_TAX_RATE = "INPUT"  # "GST on Expenses"

# --- Accounts the agent must never write to ------------------------------

# Owned by the existing Etsy<->Xero integration. Guard against double-entry.
RESERVED_ETSY_PREFIX = "ET-"


@dataclass(frozen=True)
class ExpenseCategory:
    code: str
    name: str
    tax_rate: str  # Xero TaxType: INPUT (GST on Expenses), EXEMPTEXPENSES,
    # BASEXCLUDED
    hint: str  # guidance given to Claude when categorising a receipt


# Expense categories available to the Gmail receipt flow. `hint` is what the
# model sees, so it should describe the kind of purchase, not restate the name.
EXPENSE_CATEGORIES: tuple[ExpenseCategory, ...] = (
    ExpenseCategory("400", "Advertising", "INPUT", "Ads, promotion, marketing spend."),
    ExpenseCategory("404", "Bank Fees", "EXEMPTEXPENSES", "Bank and merchant account fees. GST free."),
    ExpenseCategory("412", "Consulting & Accounting", "INPUT", "Accountant, bookkeeper, consultants."),
    ExpenseCategory("429", "General Expenses", "INPUT", "Fallback when nothing else fits."),
    ExpenseCategory("433", "Insurance", "INPUT", "Business insurance premiums."),
    ExpenseCategory("441", "Legal expenses", "INPUT", "Solicitors, legal/trademark filings."),
    ExpenseCategory("449", "Motor Vehicle Expenses", "INPUT", "Fuel, servicing, vehicle running costs."),
    ExpenseCategory("453", "Office Expenses", "INPUT", "General office supplies and consumables."),
    ExpenseCategory("461", "Printing & Stationery", "INPUT", "Printing, paper, packaging stationery."),
    ExpenseCategory("469", "Rent", "INPUT", "Premises or storage rent."),
    ExpenseCategory("473", "Repairs and Maintenance", "INPUT", "Repairs to equipment or premises."),
    ExpenseCategory("485", "Subscriptions", "INPUT", "SaaS and software subscriptions (Canva, Dropbox, hosting)."),
    ExpenseCategory("489", "Telephone & Internet", "INPUT", "Phone and internet services."),
    ExpenseCategory("493", "Travel - National", "INPUT", "Domestic travel, accommodation, transport."),
    ExpenseCategory("494", "Travel - International", "EXEMPTEXPENSES", "Overseas travel. GST free."),
    ExpenseCategory("710", "Office Equipment", "INPUT", "Capital office equipment purchases."),
    ExpenseCategory("720", "Computer Equipment", "INPUT", "Computers, phones, hardware."),
)

DEFAULT_EXPENSE = EXPENSE_CATEGORIES[3]  # 429 General Expenses

_BY_CODE = {c.code: c for c in EXPENSE_CATEGORIES}


def get_expense_category(code: str) -> ExpenseCategory:
    """Resolve a code the model chose, falling back to General Expenses."""
    return _BY_CODE.get(code, DEFAULT_EXPENSE)


def is_reserved(account_code: str) -> bool:
    """True for accounts owned by the Etsy<->Xero integration."""
    return account_code.upper().startswith(RESERVED_ETSY_PREFIX)


def assert_writable(account_code: str) -> None:
    """Guard called before any Xero write the agent performs."""
    if is_reserved(account_code):
        raise ValueError(
            f"Account {account_code} is managed by the Etsy<->Xero integration; "
            "the agent must not post to it (double-entry risk)."
        )


def categories_for_prompt() -> str:
    """Render the expense options for Claude's categorisation prompt."""
    return "\n".join(f"{c.code} - {c.name}: {c.hint}" for c in EXPENSE_CATEGORIES)
