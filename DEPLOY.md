# Deploying the Tryvis Inventory System

A standalone Django project with its own repo, its own Render service and its
own logins — running on the **same Supabase Postgres** that serves
www.tryvis.co.tz.

## How one database holds two projects

Two Django projects cannot simply point at the same database. Both want a table
called `django_migrations`, both want `auth_user`, both want
`django_content_type`. The second one to migrate would collide with the first.

The fix is a Postgres **schema**. This project lives entirely inside a schema
called `inventory`:

```
postgres (database)
├── public      ← the website: its auth_user, its django_migrations, its pages
└── inventory   ← this project: its own auth_user, its own everything
```

`DB_SCHEMA` sets it, and the connection carries `search_path=inventory` — with
no `public` fallback, on purpose. Postgres falls back silently: with
`inventory,public` in the path, any table missing from `inventory` is looked up
in `public` instead, and Django would happily read the **website's**
`django_migrations` and `auth_user` as though they were its own. The symptom is
an `InconsistentMigrationHistory` error naming `admin.0001_initial`. Leaving
`public` out means a misconfiguration fails loudly instead.

One Supabase bill, one backup, two independent systems.

Run `python manage.py init_schema` once before the first migrate, then
`python manage.py db_status` to confirm which schema you are actually in.

Because the auth tables are separate, the three inventory logins are separate
from the website admin logins. For a system where stock data stays internal,
that separation is a feature, not a cost.

### Use the session pooler, not the transaction pooler

Your website env points at port **6543**, Supabase's transaction pooler. This
project should use port **5432**, the session pooler, for two reasons:

1. The stock ledger takes row locks (`SELECT ... FOR UPDATE`) inside
   transactions so two shopkeepers cannot hand out the same item code or
   oversell the same bearing. Session connections are the calm place for that.
2. `search_path` is a session-level setting. On a transaction pooler the server
   connection can change between transactions and the setting may not follow.

`init_schema` creates the schema and nothing else. It deliberately avoids
`ALTER ROLE ... SET search_path`: on Supabase both projects normally sign in as
the same `postgres` user, so pinning a default at the role level would follow
the **website's** connections too and hide its `public` tables from it. The
schema is set per connection instead, in `DATABASES["default"]["OPTIONS"]`.

If you ever want that belt-and-braces role default, create a dedicated role for
this project first, so the setting cannot reach the website:

```sql
CREATE ROLE inventory_app LOGIN PASSWORD '...';
GRANT ALL ON SCHEMA inventory TO inventory_app;
ALTER ROLE inventory_app SET search_path TO inventory;
```

## Local setup

```bash
git clone <repo> && cd tryvis-inventory
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in the Supabase details

python manage.py init_schema  # creates the "inventory" schema
python manage.py db_status    # confirm: current schema must read "inventory"
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_inventory
python manage.py runserver
```

To try it without touching Supabase at all, set `USE_SQLITE=True` in `.env`.

`seed_inventory` loads ten realistic items across six categories, two
suppliers, two customers and opening balances — with one item deliberately
below its minimum so the alert can be demonstrated. Run
`seed_inventory --reset` to clear it before the real stock goes in.

## Render

`render.yaml` defines both services. Create an environment group called
**tryvis-inventory-env** in the dashboard holding the database and email
variables, so the web service and the cron job always read the same values.

| Service | What it does |
|---|---|
| `tryvis-inventory` (web) | `build.sh` then gunicorn. The build runs `init_schema` and `migrate`. |
| `tryvis-inventory-low-stock-alert` (cron) | `send_low_stock_alerts` at 08:00 EAT, Monday to Saturday. |

Point a subdomain such as `inventory.tryvis.co.tz` at the web service and add
it to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.

**Note on the free tier:** a Render free web service sleeps after inactivity,
and a cold start takes around a minute. For a system three people open all day
that is irritating rather than fatal, but the Starter plan is the honest
recommendation for a paying client.

## The three users

Create them in `/admin/` under **Accounts → Users**:

- one **Manager** — sees cost, margin, purchases, reports and setup
- two **Shopkeepers** — stock, quotations, invoices, delivery notes, job cards

Tick *receives stock alerts* for whoever should get the daily email. Cost price,
margin and stock value are hidden from Shopkeepers everywhere: list columns,
detail pages, reports and the admin alike.

## URLs

| Area | Who | Path |
|---|---|---|
| Sign in | — | `/login/` |
| Dashboard | Both | `/app/` |
| Items, stock adjustment, movement ledger | Both | `/app/items/` |
| Quotations, invoices, delivery notes | Both | `/app/quotations/` |
| Job cards | Both | `/app/jobs/` |
| Goods received and landed cost | Manager | `/app/purchases/` |
| Fast/slow moving, valuation, gross profit | Manager | `/app/reports/movement/` |
| Categories, units, suppliers, users | Manager | `/admin/` |

## Tests

```bash
USE_SQLITE=True DEBUG=True python manage.py test
```

28 tests. Most of them exist because something was genuinely wrong once: an
invoice that could hand out the same goods twice, a success message that
reported the quantity from before the movement, freight that lost a few
shillings to rounding, an item with no minimum counted as low on one screen and
not on another, and a setup page from which the only manager could lock
themselves out. Each test names the bug it guards.

## Verified before handover

Run against a real database, not assumed:

- 39 pages render for the Manager, 24 for a Shopkeeper, zero failures
- A Shopkeeper is refused on all 15 Manager-only pages, with no leaks
- Anonymous visitors are redirected to `/login/`
- An imported USD purchase with freight, duty and clearing allocated correctly:
  supplier price 3.10 USD → landed cost 12,560 TZS per piece
- Quotation → invoice → delivery note, with stock moving only on confirmation
- Job card issuing materials at weighted average cost
- Oversell refused with a clear message instead of negative stock
- Invoice exported as a real PDF
- Low-stock email sent once, silent on the second run

## If the two systems ever need to talk

Right now they do not — stock stays internal, which is what the client asked
for. If that changes later, the website can read a small, read-only view rather
than the tables themselves:

```sql
CREATE VIEW public.stock_availability AS
SELECT code, name, part_number,
       CASE WHEN quantity_on_hand > 0 THEN 'In stock' ELSE 'On order' END AS availability
FROM inventory.catalog_item
WHERE is_active AND item_type = 'STOCK';
```

Quantities and costs stay hidden; the website only learns whether something is
available. That is the safe shape for it if the question ever comes up.
