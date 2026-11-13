# Final review and presentation guide

## What changed

| File | Reason for the change |
| --- | --- |
| salon_core.py | Replaced dynamic method wrapping, reflection and monkey patching with direct permission checks. Added one small helper to enforce cashier attribution. Removed an unused Path import and a duplicate timedelta alias; moved time imports to the module level. Replaced floating-point report sums with readable Decimal loops. Forecast history now ends yesterday and excludes future records. Added sale-type and date validation. |
| app.py | Kept the existing screens and design. Used the existing escape import instead of dynamic importing. Aligned forecast dates with historical data. Removed an outdated demo-data caption. |
| .gitignore | Removed duplicate patterns and excluded database sidecars, backups, credentials, caches and virtual environments. |
| requirements.txt and requirements-dev.txt | Separated application dependencies from test dependencies without duplicate pytest requirements. |
| README.md | Rewritten around the implemented application, setup, examples, OOP and limitations. |
| SUBMISSION_README.md | Removed obsolete role-selector instructions; points to the current instructions. |
| SECURITY_AND_CORRECTIONS.md | Clarified audit identity and the full-payment workflow. |
| tests/test_salon_core.py | Added forecast history, transaction-type and exact-report regression checks. |
| PROJECT_REVIEW.md | This change explanation and presentation guide. |

No files were deleted. The original model classes and development notebook are
retained because they contain tested functionality and coursework history. The
older cashier summary API is still used by regression tests and is retained for
compatibility; the visible dashboard uses Cash/Mobile Money collections.

## Explaining the design

Start with three layers: Streamlit gathers input, business objects validate and
calculate, and SalonDatabase stores and retrieves records. The original models
under src/models demonstrate object composition separately from the integrated
database workflow. Explain this distinction rather than claiming both sets of
classes drive the interface.

- Encapsulation: Employee and sale objects validate themselves. Frozen model
  dataclasses resist accidental edits. Database methods control access and writes.
- Abstraction: Transaction says every transaction must calculate a total.
- Inheritance: ServiceTransaction and ProductTransaction extend Transaction.
- Polymorphism: record_sale calls calculate_total without repeating the service
  and product calculation logic. The forecast screen selects either forecast class.
- Composition: ServiceSale has ServiceAssignment objects, each holding an Employee.

## A short presentation

1. Explain the paper-record problem and show the salon name and login screen.
2. As manager, register employees, a cashier login and an allowance.
3. As cashier, record a service with full payment, then a product sale and expense.
4. Show Cash plus Mobile Money equalling total collected on the cashier dashboard.
5. Show service employees without exposing wage rates to the cashier.
6. As manager, show employee revenue and expected wages. For UGX 150,000 shared
   60/40 at wage rates 30/35, expected wages are UGX 27,000 and UGX 21,000.
7. Correct an entry with a reason and show before/after audit values. Explain that
   cashiers can edit their own transactions dated today in Kampala time only.
8. Show both forecast methods and explain their limited historical evidence.
9. Run pytest and explain that temporary databases keep tests away from real data.

## Data and security boundaries

No live record needs to change during this review. Additive schema migrations and
the earlier authorized historical-Cash migration remain intact. Do not re-run that
migration by deleting its marker. Login accounts, password hashes and sessions
are inside the ignored SQLite database. Git exclusions protect future additions;
they do not erase anything already published in repository history.

The app is a coursework project, not a production identity or payroll service.
Expected wages are estimates; expenses reduce receipts, and forecast values are
illustrative. See README.md for remaining limitations and future work.

## Verification results

- Full pytest run: 359 tests passed, including Streamlit interaction tests.
- Temporary headless Streamlit server: health endpoint returned HTTP 200; the
  test server was stopped afterwards without using the live database.
- Import review found no unused top-level imports in the app, core or model files.
- Git whitespace check passed. Database, SQLite sidecar, environment, secret-file,
  virtual-environment and credential-file exclusion examples were verified.
- No database or credential paths matching the checked patterns were tracked.
- No files were deleted, and no commit or push was made.

The existing tests/auth_helpers.py, tests/test_app_access.py,
tests/test_corrections_auth.py and tests/test_salon_identity.py continue to cover
the earlier account, cashier and correction work; they were retained intact in
this review. New review regression cases are in tests/test_salon_core.py.
