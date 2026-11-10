# Saloon-management-system
Python OOP system for salon revenue reconciliation, employee productivity and forecasting Visibility

Model validation requires non-empty text, a boolean employee status, and a valid
`PricingType`. Fixed prices and calculation inputs are converted to `Decimal`;
booleans, malformed numbers, infinity, NaN, and non-positive prices are rejected.
Use strings or `Decimal` values for money to avoid prior floating-point rounding.
Calculations keep their full decimal precision without rounding to currency units.

The models are frozen dataclasses so ordinary field assignment cannot bypass
validation. To change a record, create a validated replacement, for example:

```python
from dataclasses import replace

inactive_employee = replace(employee, active=False)
```

Contribution percentages remain greater than zero and at most 100; wage rates
remain between zero and 100, with a default of 30. Variable services have no fixed
price. Assignments do not impose employee status or department restrictions.

Run the regression tests on Windows with:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```
