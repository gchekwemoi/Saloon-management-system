# Saloon Management System – MSc Object-Oriented Programming Prototype

**Repository:** https://github.com/gchekwemoi/Saloon-management-system

## What the prototype demonstrates

- **OOP:** abstract `Transaction`, inherited `ServiceTransaction` and `ProductTransaction`, polymorphic `calculate_total()`, validation/encapsulation and composition in existing service assignments.
- **Cashier:** service sales with negotiated prices and multiple employee allocation, retail sales, cash/mobile money receipts, expenses within manager-approved allowances.
- **Owner/Manager:** employee registration with individual wage rates, approved allowances, reconciliation, productivity and simple revenue forecasts.
- **Storage:** SQLite database file `salon.sqlite3`, created automatically.

**Limitations:** The role selector is a classroom demonstration, not secure authentication. Mobile money is recorded manually; there is no API integration. Expected wages are not verified wage payments. Forecast results depend on available history. This is a teaching prototype, not production-ready financial software.

## Run with Anaconda / JupyterLab

1. Extract the ZIP's files directly into the existing `Saloon-management-system` project folder. Keep `src/` and your original project classes. Do not overwrite or delete existing files.
2. In JupyterLab choose **File > New > Terminal** from inside that project folder.
3. Install dependencies: `python -m pip install -r requirements.txt`
4. Start the interface: `python -m streamlit run app.py`
5. Open the local URL shown in the terminal, usually `http://localhost:8501`.
6. In the demo, select **Owner/Manager** to add employees and approve an allowance. Then select **Cashier** to record a service, allocate 100% of employee shares, add a payment or product sale, and record an expense. Return to Owner/Manager to view reconciliation and forecasts.

## Run tests

`python -m pytest -q`

## Suggested demonstration

Register two employees with expected wage rates of 30% and 35%. Record a variable-price braiding service of UGX 150,000, assign 60% and 40%, and collect UGX 120,000 cash. Expected wages: UGX 27,000 and UGX 21,000; unpaid client balance: UGX 30,000. Add a product sale and a manager-approved expense. Inspect reports.

## Implementation note

`salon_core.py` provides the integrated application layer and a separate abstract `Transaction` demonstration without modifying the earlier coursework `ServiceSale` and local `ProductSale` classes. A later production refactor should consolidate these parallel transaction representations and replace the demo role selector with authenticated permissions. The application validates new service allocations against registered active employees.
