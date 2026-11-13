# Accounts and corrections

The existing SQLite database is upgraded in place on startup. Account, session,
and correction audit tables are added without replacing business tables or rows.
Back up the SQLite file using SQLite's backup facility before deploying updates.

## First manager setup

Start `python -m streamlit run app.py` and choose the first manager's username
and a password of at least 12 characters. No setup token is required. Setup
refuses to create another initial manager once any account exists. Complete this
first setup before exposing the application to other users; the first person
who completes it becomes manager.

Sign in as manager, register cashiers, then create login accounts linked to their
cashier IDs under Settings & Cashiers. Existing cashier records are preserved;
they do not automatically receive passwords. Managers can also create additional
manager accounts. Role switching has been removed.

Passwords use independently salted PBKDF2-HMAC-SHA256 (600,000 iterations).
Sessions use random bearer tokens, stored hashed in SQLite, with eight-hour expiry
and server-side logout revocation. Business methods check sessions and roles;
cashier submissions cannot choose another cashier or change administrative data.
Wage fields are excluded from cashier-facing employee and sale results.

## Corrections

Cashiers can edit their own transactions dated today under Sales Register,
using Kampala time (UTC+3). The backend checks ownership and date within the
correction transaction. After midnight, a manager must make corrections.
Cashiers may correct amounts, descriptions, and payment method/reference; changing
dates, cashier identity, employee allocations, sale links, or allowances requires
a manager. Cashier corrections use the same audit log and financial validation.

Managers select a register and record under Corrections. Service allocations use
one `employee ID,percentage` per line, totaling exactly 100%. Existing assigned
employees retain the wage rate recorded on the sale; new employees use current
rates. Product corrections adjust the recorded total (legacy sales do not store
quantity or unit price separately). Record IDs and sale kinds remain stable.

Every successful correction records full before/after values, assignments where
applicable, reason, UTC timestamp and the correcting account username. A SQLite immediate write
transaction validates and saves the correction and audit together. Invalid
allocations, overpayments and allowance overspending roll back completely.
Summaries, productivity and allowance balances are derived from current records.

## Limits

This is basic application authentication, not a hardened hosted identity service.
Use HTTPS and trusted server/file access. Anyone with direct SQLite file or Python
process access can bypass application controls or alter audit records. There is no
MFA, password recovery UI, account disabling UI, or login rate limiting yet. Sessions
expire after eight hours and require login again after logout or a lost browser
session. Audit history is retained in SQLite, not an external tamper-proof store.
The original raw database connection API remains available for migrations and tests.

New sales include full Cash or Mobile Money payment. The earlier user-approved
one-time migration settled historical unpaid balances as Cash with audit entries.
It must not be repeated by clearing the migration marker. Cashier collection cards
are all-time totals for sales recorded by that cashier, including payments recorded
by another cashier against those sales.
