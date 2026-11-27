# Order-to-Audit: a small food manufacturer system

Internship shortlisting task, Centre for Digital Infrastructure, NIT Tiruchirappalli.
Built by Pothiswaran Thangamani.

One system that takes a snack factory from a salesman's order to the auditor's monthly report.
Every transaction is entered once, at its source, and flows into stock, production, costing and accounts.

- **Demo video:** (paste the unlisted YouTube or Drive link here)
- **Design note:** [docs/DESIGN.md](docs/DESIGN.md)

## Run it

### Option 1: one Docker command

```
docker compose up --build
```

Open http://localhost:8000 and log in with a demo user below.

### Option 2: without Docker (Python 3.12 or newer)

```
python -m venv venv
venv\Scripts\activate          (on Mac or Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py setup_demo
python manage.py runserver
```

`setup_demo` creates the tables, loads the section 5 master data and opening stock, creates the five roles and the demo users.
It is safe to run again.

Run the automated tests with `python manage.py test`.

## Test logins

Every user has the password **Demo@12345**.

| Role | Username | What they can do |
|---|---|---|
| Salesman | `salesman_a`, `salesman_b` | Phone-friendly order entry, their own orders and customer-wise sales |
| Factory admin | `factory_admin` | Review and approve orders, GST invoices, dispatch, payments, credit notes, masters |
| Production supervisor | `production_sup` | Purchases, production runs, overheads, stock |
| Accountant | `accountant` | Read-only reports, dashboard and audit trail, with exports |
| Owner | `owner` | Dashboard and the same read-only reports |
| Superuser | `demo_admin` | Everything, including the admin site |

Log in at `/accounts/login/`. The home page shows only what the role may open.

## Stack and why

Python with Django and SQLite. Django gives login, groups and permissions for the roles, an ORM with exact `Decimal` money, transactions that make every posting all-or-nothing, and ready-made data entry screens for masters. The mobile pages are plain responsive HTML with no JavaScript framework, so they load quickly on a weak network. SQLite needs no setup, and the same models run on PostgreSQL.

## What is built, against the section 6 tiers

**Must have: all built.** Login with five roles; product, customer, raw-material and BOM masters; mobile order entry and admin approval; GST invoice as PDF; production run that updates raw-material and finished-goods stock; planned against actual consumption and yield with variance; stock summary and stock ledger; sales register and stock report with CSV, Excel and PDF export.

**Should have: all built.** Purchases and supplier records; payments, outstanding and ageing; cost per packet with overheads; GST summary (GSTR-1 and GSTR-3B shape); variance alerts beyond a 3% tolerance; owner dashboard.

**Beyond the list:** credit notes (a posted invoice is cancelled, never deleted); an audit trail of who created, changed or deleted key records; free-stock reservation (approved orders claim stock, so the same packets are not promised twice); HSN summary and credit notes register; 13 reports in all, each exportable to CSV, Excel and PDF; over 70 automated tests that re-run the benchmark.

**Stretch goals from the list:** none attempted.

## Benchmark results (section 5)

Every figure matches the problem statement. The automated tests check each one.

| Check | Expected | This system |
|---|---|---|
| Flour closing balance | 120 kg | 120 kg |
| Oil closing balance | 19.5 L | 19.5 L |
| Pouches closing balance | 306 | 306 (188 used + 6 damaged) |
| Finished goods after run | 238 | 238 |
| Finished goods after Retailer A dispatch | 88 | 88 |
| Yield variance | 188 vs 200, -6%, flagged | -6.00%, flagged |
| Oil consumption variance | +5%, flagged | +5.00%, flagged |
| Retailer A invoice | 7,500 + 187.50 + 187.50 = 7,875 | 7,875.00 |
| Retailer A outstanding | 3,875 | 3,875.00 |
| Distributor B order | Shortage of 32, IGST if invoiced | "Short by 32", approval blocked; invoicing it gives IGST 300.00 on 6,000.00 (tested) |
| Cost per packet | My figure | **Rs 31.14**, margin Rs 18.86 (37.71%) |

Notes on the figures:
- **Cost per packet:** materials Rs 4,055.00 (flour 1,725.00, oil 1,470.00, spice mix 240.00, pouches 485.00, cartons 135.00) plus labour 1,200 and gas/power 600 gives Rs 5,855.00, divided by 188 good packets. Weighted-average method, overheads charged to the run.
- **Cartons are flagged at -10%:** 9 cartons were used against 10 planned.
- **Pouches are not flagged:** 194 used against 200 planned is -3.00%, which is not beyond the 3% tolerance.

## How it works (short version)

- **Stock is never typed in.** Every movement (opening, purchase, production issue, wastage, output, dispatch, adjustment) is one signed row in a ledger with its source document. A balance is the sum of the rows. Ledger rows cannot be edited or deleted; mistakes are fixed with an adjustment row.
- **Costing uses weighted average.** Flour was Rs 42 in opening stock and Rs 45 in the new purchase, so the run is charged Rs 43.125 per kg. Last price would overstate the cost and FIFO needs lot tracking. Details are in the design note.
- **Overheads** are recorded against a run and spread over its good packets.
- **GST:** a customer in Tamil Nadu is charged CGST + SGST, in another state IGST. Invoice numbers run by financial year (INV/2026-27/0001).
- **Money** uses `Decimal` throughout, rounded to the paisa.

## Assumptions

- The item rate of a raw or packaging item is its opening rate. The rate of a finished product is its selling price (the price list).
- GST is 5% on every item (a field on the item). HSN 21069099, the seller details, and all GSTINs are invented demo values.
- An approved, not yet dispatched order claims stock; a shortage blocks approval until the quantity is reduced or the order is rejected.
- One order becomes one invoice. Dispatch is for the whole invoice.
- Ageing is counted from the invoice date, not a credit due date.
- Damaged items are a cost of the run, but cost per packet divides by good packets only.
- Saved payments, overheads and invoices are not edited. A negative overhead corrects an entry, a credit note cancels an invoice, and a negative outstanding means a refund is due.
- The demo uses the Django development server, DEBUG on and SQLite.

## Known gaps

- **Unit conversion:** each item has one unit and quantities are entered in it. Automatic conversion between kg and g, litre and ml, and cartons of packets is not built yet.
- A recipe belongs to one product, so a second pack size that shares a recipe is not modelled yet.
- No offline order capture, batch or expiry tracking, reorder alerts, or partial dispatch.
- Credit notes are full only. There is no partial return and no refund payment screen.
- No Tally export, e-invoice format or Tamil interface.
- The audit trail sees changes made through the application, not direct database edits, and it does not log logins.
- Not hardened for production (secret key, debug mode, SQLite file, development server).

## Use of AI assistance

I used an AI assistant (Claude) as a coding guide while building this, as the problem statement allows. I built it step by step in my own repository, ran every step and test myself, and can explain each part.

## Project layout

| Folder | Purpose |
|---|---|
| `masters` | Items, BOM, customers, suppliers; seed data and role setup commands; permissions |
| `inventory` | Stock ledger, balances, purchases, stock summary |
| `production` | Production runs, variance, costing |
| `sales` | Salesman orders, admin review and the stock check |
| `billing` | GST invoices and PDF, dispatch, payments and ageing, credit notes |
| `reports` | Reports with CSV, Excel and PDF export, owner dashboard |
| `audit` | Audit trail of who changed what, and when |