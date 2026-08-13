# Chart of Accounts — Paper&Petals

Xero, Australia (GST / BAS). Exported 13 Aug 2026. Reference copy for the agent's
account mapping (`app/accounting/coa.py`).

## Agent scope

| Area | Owner |
|------|-------|
| **Etsy sales & Etsy fees** | **Existing Etsy↔Xero integration — NOT the agent.** These land in the `ET-*` accounts automatically. The agent must never post them (double-count risk). |
| **App subscription income** (RevenueCat / Apple / Google) | **The agent** → `200 Sales` |
| **Supplier receipts from Gmail** | **The agent** → mapped expense accounts below |
| **Etsy listings / inventory** | The agent (non-financial) |

## Revenue

| Code | Account | Type | GST |
|------|---------|------|-----|
| 200 | Sales | Revenue | GST on Income |
| 260 | Other Revenue | Revenue | GST on Income |
| 270 | Interest Income | Revenue | GST Free Income |

## Expenses

| Code | Account | GST |
|------|---------|-----|
| 400 | Advertising | GST on Expenses |
| 404 | Bank Fees | GST Free Expenses |
| 412 | Consulting & Accounting | GST on Expenses |
| 416 | Depreciation | BAS Excluded |
| 429 | General Expenses | GST on Expenses |
| 433 | Insurance | GST on Expenses |
| 437 | Interest Expense | GST Free Expenses |
| 441 | Legal expenses | GST on Expenses |
| 449 | Motor Vehicle Expenses | GST on Expenses |
| 453 | Office Expenses | GST on Expenses |
| 461 | Printing & Stationery | GST on Expenses |
| 469 | Rent | GST on Expenses |
| 473 | Repairs and Maintenance | GST on Expenses |
| 477 | Wages and Salaries | BAS Excluded |
| 478 | Superannuation | BAS Excluded |
| 485 | Subscriptions | GST on Expenses |
| 489 | Telephone & Internet | GST on Expenses |
| 493 | Travel - National | GST on Expenses |
| 494 | Travel - International | GST Free Expenses |
| 505 | Income Tax Expense | BAS Excluded |

## Assets / Liabilities / Equity (not written by the agent)

610 Accounts Receivable · 620 Prepayments · 710 Office Equipment ·
711 Accum. Depreciation (Office) · 720 Computer Equipment ·
721 Accum. Depreciation (Computer) · 800 Accounts Payable ·
801 Unpaid Expense Claims · 804 Wages Payable · 820 GST ·
825 PAYG Withholdings Payable · 826 Superannuation Payable ·
830 Income Tax Payable · 840 Historical Adjustment · 850 Suspense ·
860 Rounding · 877 Tracking Transfers · 880 Gemma Manns - Drawings ·
881 Gemma Manns - Funds Introduced · 900 Loan · 960 Retained Earnings ·
Trading Account (Bank)

## Etsy accounts — reserved, do not write

Managed by the Etsy↔Xero integration:

`ET-00000` Etsy Payment Balance (Bank) · `ET-20000` Etsy Other Income ·
`ET-20001/2` Etsy Sales (Domestic/International) ·
`ET-20003/4` Etsy Coupon (Dom/Intl) · `ET-20005/6` Etsy Gift Wrap (Dom/Intl) ·
`ET-20007/8` Etsy Shipping/Delivery Fee Revenue (Dom/Intl) ·
`ET-60000` Etsy Adjustments · `ET-70000/70004` Etsy Collected Taxes (Dom/Intl) ·
`ET-80000` Etsy Fees · `ET-80001` Etsy Advertising · `ET-80002` Etsy Chargeback ·
`ET-80003` Etsy Shipping Label

`coa.assert_writable()` raises on any `ET-` code as a safety net.

## Open question — GST on app subscription income ⚠️

All agent-booked income posts to **200 Sales**, which carries **GST on Income**.
That is correct for **domestic (Australian) sales**. Two things to confirm with
your accountant:

1. **International app sales** are typically **GST-free exports**, not GST on
   Income. Booking everything at GST on Income would over-report GST.
2. **Apple/Google often collect and remit consumption tax themselves** in many
   jurisdictions, which changes what you should book as your own GST liability.

Until confirmed, the agent posts income to 200 with GST on Income and flags
non-domestic subscription revenue in the review queue rather than guessing.
