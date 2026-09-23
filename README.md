# Tryvis Inventory Management System

A standalone Django project. PostgreSQL on Supabase — the same instance as the
tryvis.co.tz website, kept apart in its own schema. Deployed on Render.
Interface language: English.

Start with `DEPLOY.md`.

## Apps

```
tryvis-inventory/
├── config/          settings, urls, wsgi
├── core/ accounts/ catalog/ inventory/ purchasing/ sales/ jobs/
├── templates/       UI, printable documents, alert emails
├── render.yaml      web service + nightly cron job
└── build.sh         collectstatic, init_schema, migrate
```

| App | Holds |
|---|---|
| `config` | Project settings, routing, login |
| `core` | Timestamps, created-by, gap-free document numbering, schema bootstrap, PDF helper |
| `accounts` | Custom `User` with Manager / Shopkeeper roles |
| `catalog` | Units, categories, suppliers, items, item-code generation |
| `inventory` | Stock movement ledger, costing, low-stock alerts, movement analysis |
| `purchasing` | Goods received notes and landed-cost allocation |
| `sales` | Customers, quotation → invoice → delivery note |
| `jobs` | Workshop job cards, materials issued, job costing |

## Item codes

Format `TIL-BRG-001`: company prefix, category code, sequence within the category.

- The prefix lives in `settings.ITEM_CODE_COMPANY_PREFIX`.
- The sequence counter sits on `Category` and is handed out under a row lock, so two shopkeepers saving at the same second can never get the same code.
- `part_number` is a separate, indexed field. `6204` is what the customer says on the phone; the system code is for the store.
- `barcode` exists but is unused for now — it is there so a scanner can be added later without a migration on live data.

## The three item types

| Type | Stock tracked | Example |
|---|---|---|
| `STOCK` | Yes | Bearings, cutting discs — bought to resell |
| `CONSUMABLE` | Yes | Welding rods, grease — used on jobs |
| `SERVICE` | No | Labour, machining — appears on documents, never on a stock report |

## Stock ledger

`StockMovement` is the only thing that changes stock. Rows are never edited or deleted — a mistake is fixed with an opposite movement, so the history always adds up. `Item.quantity_on_hand` is a running total kept for speed, and `Item.recalculate_quantity()` can rebuild it from the ledger during an audit.

Every movement goes through `record_movement()`, which locks the item row, refuses to take out more than exists, and keeps the weighted average cost correct.

## Landed cost

A purchase header carries `freight_cost`, `customs_duty`, `clearing_charges` and `other_charges`, plus currency and exchange rate. On `purchase.receive()` those charges are spread over the lines — by value, quantity or weight — and each line gets a `landed_unit_cost`. That figure, not the supplier's invoice price, is what feeds every profit number in the system.

## Document flow

```
Quotation  ──convert_to_invoice()──▶  Invoice  ──create_delivery_note()──▶  Delivery Note
  (no stock effect)                  (no stock effect)                  confirm_delivery()
                                                                              │
                                                                              ▼
                                                                    stock leaves the store
```

**Decision worth confirming with the client:** stock is deducted on the delivery note, not the invoice. An invoice can be raised days before goods are collected, and the ledger should show what physically happened. If they would rather have stock move the moment an invoice is issued, `Invoice.create_delivery_note()` can simply be followed by `confirm_delivery()` in the same step.

## Roles

- **Manager** — everything: cost, margin, purchases, reports, user setup.
- **Shopkeeper** — receive stock, issue stock, raise quotations, invoices, delivery notes and job cards. Cost price, margin and company-wide reports are hidden.

The role sits on the user record itself. This project owns its auth tables, so the inventory logins are separate from the website's.

## Low-stock alerts

Email only. `python manage.py send_low_stock_alerts` runs each morning as a Render Cron Job (defined in `render.yaml`) and mails every user with `receives_stock_alerts = True`. `StockAlertLog` keeps an item from being reported again until it has been restocked and falls low a second time.

## Fast / slow moving

`inventory/reports.py` classifies each item by turnover over a window (90 days by default):

- **FAST** — turnover ≥ 2.0
- **NORMAL** — 0.5 to 2.0
- **SLOW** — below 0.5, but something moved
- **DEAD** — nothing moved at all, yet stock is held

`dead_stock_value()` gives the manager the one number that usually starts a conversation: money sitting still.

## Documents

Quotations, invoices and delivery notes print from `/app/print/<type>/<id>/`,
laid out on A4 with the company header, signature blocks and per-document
footer terms. Add `?pdf=1` for a real PDF file — `xhtml2pdf` is in
`requirements.txt`; without it the same page still prints from the browser.
Company name, address, TIN and VAT rate all come from environment variables.

## Still to decide

1. Stock on delivery note vs on invoice (see above).
2. Does the manager want customer payments tracked, or is `amount_paid` on the invoice enough?
3. VAT — is Tryvis VAT registered? `VAT_RATE` is set to 18% and can be switched off per document.
