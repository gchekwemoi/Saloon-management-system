# Saloon Management System

This is my MSc Data Science Object-Oriented Programming coursework project. It helps a salon record sales, allocate employee revenue, estimate wages and compare receipts with expenses.

## Problem and objectives

Paper records make it difficult to know who served a customer, who collected money and how much each employee contributed. The objectives are to keep records together, validate financial calculations, separate staff permissions and provide simple management reports.

## Implemented features

- Owner/Manager and Cashier login accounts, hashed passwords and backend permission checks.
- Configurable salon name, multiple cashiers and individual usernames linked to cashier records.
- Employee registration with departments and individual wage percentages.
- Flexible service prices and employee allocations totaling exactly 100%.
- Product sales using quantity and agreed unit price.
- Full Cash or Mobile Money payment saved together with each new sale. Mobile Money references are entered manually.
- Approved allowances and expenses limited to the remaining balance.
- Cashier dashboard with total collections, Cash, Mobile Money, products, expenses and service employees. Totals cover all sales recorded by that cashier.
- Manager reconciliation, employee productivity and cashier activity reports.
- Filtered CSV report downloads for sales, payments, expenses and employee allocations. Select dates, cashier, applicable sale type or payment method, and detailed/daily/weekly/monthly output. Frequency groups results; it does not schedule email reports.
- Corrections with reasons, timestamps and before/after audit values. Cashiers may edit their own transactions dated today in Kampala time; managers may correct older records and allocations.
- Moving-average and weekday-pattern forecasts for seven days.
- SQLite persistence with additive migrations. The approved one-time migration settles historical unpaid balances as Cash and records audit entries.

## Technology and folder structure

Python, Streamlit, pandas, SQLite, Decimal and pytest are used. Python includes SQLite; a separate database server is not needed.

```text
app.py                         Streamlit forms, navigation and theme
salon_core.py                  Business classes, access checks and SQLite storage
reporting.py                   Period summaries and CSV export helpers
src/models/                    Original validated coursework models
tests/                         Model, finance, security and Streamlit tests
.streamlit/config.toml         Theme settings
requirements.txt               Application dependencies
requirements-dev.txt           Application and testing dependencies
SECURITY_AND_CORRECTIONS.md    Account and correction details
PROJECT_REVIEW.md              Review and presentation guide
salon_development.ipynb        Earlier development notebook
```

The notebook and original model classes remain as coursework material. The live app uses the integrated classes in salon_core.py; src/models is independently tested and does not maintain another database. Local databases and backups are excluded from Git.

## OOP concepts

| Concept | Implemented example |
| --- | --- |
| Encapsulation | Classes validate inputs; database methods enforce permissions and atomic writes. Original model dataclasses are frozen. |
| Abstraction | Transaction defines calculate_total(); RevenueForecaster defines forecast(). |
| Inheritance | ServiceTransaction and ProductTransaction inherit from Transaction. Both forecast classes inherit from RevenueForecaster. |
| Polymorphism | calculate_total() handles either an agreed service price or quantity times product price. The forecast page calls either implementation using forecast(). |
| Composition | ServiceSale contains a Service and ServiceAssignment objects; each assignment contains an Employee. |

Python privacy conventions do not protect data from someone with direct server access. Application permissions protect normal application use.

## Setup and running

Use Python 3.10 or later. Open a terminal in this project folder on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local address printed in the terminal. On first run, choose a manager username and a password of at least 12 characters. No default password or setup token is provided. Complete initial setup before exposing the app to other users. Existing installations keep their existing accounts.

As manager, register employees and cashiers. Under Settings & Cashiers, create individual Cashier login accounts and link each to the correct cashier record. Sign out; cashiers use the same Sign in page. The authenticated account determines access.

Always start from the same project folder to use the same salon.sqlite3 file. Keep SQLite backups before upgrades; do not replace the live database with sample data.

## Example usage

1. Register two employees with expected wage rates of 30% and 35%.
2. Register a cashier, create their login and approve a UGX 10,000 allowance.
3. As cashier, record a UGX 150,000 braiding service with employee shares of 60% and 40%. Select Cash and record full payment with the sale.
4. Employee revenue is UGX 90,000 and UGX 60,000. Expected wages are UGX 27,000 and UGX 21,000, totaling UGX 48,000.
5. Sell two products at UGX 8,000 each using Cash or Mobile Money.
6. Record a UGX 4,000 expense. The remaining allowance is UGX 6,000.
7. As manager, inspect reports. Correct errors with a reason; do not enter duplicate payments.

Expected wages are estimates, not wages already paid. Net receipts less expenses does not deduct wages and is not final profit.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover validation, allocations, expected wages, payments, allowances, correction rollback, audit history, migrations, permissions, login and dashboard behaviour. Tests use temporary databases instead of live records.

## Limitations and future improvements

- No MFA, password recovery screen, account disabling screen or login rate limiting. Restrict server access and use HTTPS when hosting.
- Audit history is in SQLite, not an external tamper-proof service.
- Product quantity and unit price are used at entry but not stored separately in the current sales table. Reports count sale records rather than stock units.
- Corrections prevent invalid allocations, overpayments and excess expense spending. Independently changing sale and payment amounts can still leave a reconciliation difference; managers must review both records.
- Forecasts are teaching examples without predictive evaluation. Missing days count as zero, and limited history reduces usefulness.
- Earlier financial APIs remain for compatibility and testing; new sales in the interface require full payment.
- Future improvements could include inventory, linked sale/payment corrections, stronger account protection and forecast evaluation.
