# Saloon Management System
## An Object-Oriented System for Sales, Employee Revenue Allocation and Reconciliation

Uganda Christian University

MSc Data Science and Analytics

CSC8101: Object-Oriented Programming

Student name: [INSERT FULL NAME]

Registration number: [INSERT REGISTRATION NUMBER]

Submission date: 13 November 2026

GitHub repository: https://github.com/gchekwemoi/Saloon-management-system

### Abstract
This project develops an object-oriented Python application for managing a salon's daily transactions. It connects service and product sales, full payments, employee contributions, expected wages and approved expenses. Streamlit provides separate interfaces for authenticated managers and cashiers, while SQLite preserves the records. Abstract classes, inheritance, polymorphism, encapsulation and composition organise the calculations and models. Managers can review reconciliation and make audited corrections; cashiers have restricted access and same-day editing of their own transactions. Two simple forecasting methods demonstrate data-driven decision support. The final software review recorded 367 passing automated tests and successful Streamlit startup. The result is a functional coursework application rather than production payroll or banking software.

<!-- PAGE -->
# 1. Introduction and Problem Statement

A unisex salon may offer braiding, barbering, hairdressing, nails and other beauty services while also selling products. Service prices can depend on the agreed style and work involved. More than one employee may serve a customer, and customers may pay using Cash or Mobile Money. If these records are kept separately, it becomes difficult to connect sales, workers, collections and operating expenses.

The problem addressed by this project is the lack of one traceable workflow for recording sales, sharing service revenue, estimating employee wages and reconciling receipts with expenses. The application uses the configured salon name, such as Baraka Unisex Saloon, and supports multiple cashiers.

## 1.1 Aim and objectives

The aim is to develop a functional salon management application that demonstrates object-oriented programming in Python. The objectives are to:

- Record flexible-price services and product sales with full payment.
- Allocate service revenue among employees and calculate expected wages.
- Control expense spending through manager-approved allowances.
- Preserve records and correction history in SQLite.
- Provide role-based dashboards, management reports and simple forecasts.

## 1.2 Scope and development approach

The proposal was submitted before this final report. Development proceeded through domain modelling, integration, interface improvements and automated regression testing. The project remains in the existing repository; the original models and database were not replaced. Customer credit, inventory control, actual wage disbursement and automatic Mobile Money collection are outside the implemented scope.

<!-- PAGE -->
# 2. Requirements and System Architecture

The application has two authenticated roles. The Owner/Manager registers employees and cashiers, creates accounts, configures the salon name, approves allowances, reviews reports and makes corrections. A Cashier records sales and expenses, views permitted activity and edits their own transactions dated today in Kampala time.

| Area | Implemented requirement |
| --- | --- |
| Sales | Positive agreed prices; product quantity must be a positive integer; service allocations total 100%. |
| Payments | Full Cash or Mobile Money payment with new sales; references required for Mobile Money. |
| Expenses | Positive amount within the remaining approved allowance. |
| Access | Authenticated account determines permissions; cashier identity is checked in business methods. |
| Reliability | Atomic writes, input validation, audit history and persistent records. |

## 2.1 Architecture

Figure 1 summarises the existing three-layer structure. Streamlit is used to build the interactive Python interface [1].

```diagram
User: Owner/Manager or Cashier
                 | submits input
app.py: forms, navigation, tables and theme
                 | calls business methods
salon_core.py: validation, permissions,
transactions, calculations and forecasting
                 | reads and writes records
salon.sqlite3: persistent business and audit records
```

Figure 1. Application architecture. The live interface uses salon_core.py.

<!-- PAGE -->
# 3. Object-Oriented Design

The project uses classes to group related data and behaviour. Python abstract base classes define operations that concrete subclasses must provide [2]. Table 1 connects the OOP concepts to the implemented code.

| Concept | Application in the project |
| --- | --- |
| Encapsulation | Model validation protects valid state; database methods enforce permissions and controlled writes. Original model dataclasses are frozen. |
| Abstraction | Transaction defines calculate_total(); RevenueForecaster defines forecast(). |
| Inheritance | ServiceTransaction and ProductTransaction inherit Transaction; both forecasting classes inherit RevenueForecaster. |
| Polymorphism | The same calculate_total() call handles service and product totals. Either forecaster can supply forecast(). |
| Composition | In src/models, ServiceSale contains a Service and assignments; each ServiceAssignment contains an Employee. |

Table 1. OOP concepts and their implementation.

```diagram
Transaction: calculate_total() (abstract)
  |-- ServiceTransaction
  `-- ProductTransaction
RevenueForecaster: forecast() (abstract)
  |-- MovingAverageForecaster
  `-- WeekdayForecaster
ServiceSale contains Service and ServiceAssignment
ServiceAssignment contains Employee
```

Figure 2. Main OOP relationships. Composition examples belong to src/models; integrated transaction classes drive the interface. Both are retained as tested coursework functionality.

<!-- PAGE -->
# 4. Sales, Allocations and Expected Wages

Employees are registered with an identifier, name, department and expected wage percentage. A completed service stores the actual agreed client price rather than imposing a standard price. One or more registered employees can be assigned, but duplicate employees, invalid percentages and allocations not totaling exactly 100% are rejected.

For employee i:

Attributed revenue = service price x contribution percentage / 100.

Expected wage = attributed revenue x recorded wage percentage / 100.

| Employee | Contribution | Attributed revenue | Wage rate | Expected wage |
| --- | --- | --- | --- | --- |
| A | 60% | UGX 90,000 | 30% | UGX 27,000 |
| B | 40% | UGX 60,000 | 35% | UGX 21,000 |
| Total | 100% | UGX 150,000 | - | UGX 48,000 |

Table 2. Worked example for a UGX 150,000 service. These are illustrative inputs, not a claim about a particular customer transaction.

ProductTransaction calculates quantity multiplied by unit price. For example, two products at UGX 8,000 produce a UGX 16,000 sale. ServiceTransaction returns the agreed service price. Calling calculate_total() on either object demonstrates polymorphism.

The program uses Decimal for monetary calculations and stores amounts as decimal strings. Decimal avoids the representation issues associated with binary floating-point values in financial calculations [3]. Reports also accumulate totals using Decimal. Displaying whole UGX amounts does not change the stored calculation precision. Expected wages are estimates, not evidence that employees have already been paid.

<!-- PAGE -->
# 5. Payments, Expenses and Reconciliation

New sales require full payment. The cashier chooses Cash or Mobile Money, and Mobile Money requires a reference. The sale, service assignments and payment are saved in one SQLite transaction. If validation or insertion fails, partial records are not committed. Mobile Money is recorded manually; there is no payment-provider integration.

The manager approves an expense allowance. A cashier selects an allowance and records a positive expense no greater than its available balance. Remaining allowance is calculated from the approved amount minus recorded spending; it is not a second revenue figure.

## 5.1 Financial reconciliation

- Total charges = service sales value + product sales value.
- Recorded receipts = sum of payment records.
- Net receipts after expenses = receipts - recorded expenses.
- Projected margin after expected wages = charges - expenses - expected wages.

For the example service of UGX 150,000, product sale of UGX 16,000 and expense of UGX 4,000, full receipts are UGX 166,000. Net receipts after expenses are UGX 162,000. Deducting estimated wages of UGX 48,000 gives a projected margin of UGX 114,000. This is not verified final profit because the system does not record every business cost or wage disbursement.

The earlier user-approved migration added Cash payments only for historical unpaid remainders. Existing payments were preserved, additions were audited and a migration marker prevents repetition. New sales do not require a separate Receive Payment screen. Manager reconciliation retains balance checks because independent corrections can still create a difference between charges and receipts.

<!-- PAGE -->
# 6. Accounts, Permissions and Interface

The first manager chooses a username and a password of at least 12 characters. Setup closes after an account exists; there is no hardcoded password or setup token. The manager registers each cashier and creates an individual login linked to the correct cashier record. Managers and cashiers use the same sign-in page.

Passwords are stored as independently salted PBKDF2-HMAC-SHA256 hashes using 600,000 iterations. Python provides PBKDF2 through hashlib [4]. Random session tokens are stored hashed, expire after eight hours and are revoked on sign-out. Permission checks in business methods prevent cashiers from selecting another cashier identity or using manager operations.

| Owner/Manager interface | Cashier interface |
| --- | --- |
| Dashboard, Employees, Settings & Cashiers | Dashboard, Record Service, Sell Product |
| Allowances, Reports, Forecasting | Record Expense, Sales Register |
| Corrections and complete audit history | Restricted same-day edits in Sales Register |

Table 3. Role-specific navigation. Cashier-facing sale and employee results exclude expected wages and wage rates.

The purple, pink, gold and black theme is retained. The sidebar identifies the signed-in account and cashier. Dashboard cards display separated UGX amounts with responsive typography. Alert and form colours improve readability. The cashier dashboard shows all-time collections for sales recorded by that cashier, split into Cash and Mobile Money, with products, expenses and service employees. Total collected equals Cash plus Mobile Money; expenses are displayed separately. No confidential wage summary is shown to cashiers.

<!-- PAGE -->
# 7. Persistence, Corrections and Audit History

SQLite stores employees, sales, assignments, payments, allowances, expenses, salon settings, cashiers, accounts, sessions and correction audits. Schema migrations add missing tables or fields without replacing business records. Python's sqlite3 module supplies access to this local, disk-based database without requiring a separate database server [5].

Sales link to employee assignments and payments. Expenses link to approved allowances. Cashier identifiers connect entries to responsible staff, and login accounts link to cashier records. Existing assignments preserve the wage rate recorded at the time of allocation.

## 7.1 Correction workflow

```diagram
Choose register and record
           |
Check account, ownership and permitted date
           |
Require reason; validate corrected values
           |
Recalculate allocations, wages and balances
           |
Save correction and audit in one transaction
```

Figure 3. Correction workflow. Invalid changes roll back instead of partially updating the record.

Managers can correct sales, payments, expenses and service allocations. Cashiers can correct their own transactions dated today in Kampala time, but cannot change dates, cashier identity, employee allocations, sale links or allowances. After midnight, a manager must make the correction. Audit entries preserve before/after values, the reason, correcting account and UTC timestamp. Invalid allocations, overpayments and excess allowance spending are rejected. This audit is application-managed, not tamper-proof against direct database access.

<!-- PAGE -->
# 8. Reports and Forecasting

Management reports combine charges, receipts, expenses, expected wages, employee productivity and cashier activity. Managers can download sales, payment, expense and employee-allocation CSV reports filtered by dates, cashier and applicable sale type or payment method. Output can be detailed, daily, weekly or monthly; frequency groups records rather than scheduling delivery. Employee revenue differs from wages. Service tables distinguish employees who performed work from the recording cashier.

## 8.1 Forecasting methods

MovingAverageForecaster uses the average of up to the last seven supplied daily totals. WeekdayForecaster looks at matching weekdays in up to four weeks of history and falls back to an overall average when matching observations are unavailable. Both implement the same forecast() operation.

The interface prepares 28 consecutive historical dates ending yesterday and forecasts seven dates beginning today. A day with no recorded sales contributes zero. Future-dated records are excluded from the historical series. A bar chart and table present the estimates. The forecast is based on sales charges rather than an external economic or customer dataset.

## 8.2 Interpretation

These methods are transparent teaching baselines. They demonstrate aggregation, algorithmic logic and visualisation within an OOP application. They have not been evaluated against held-out data, and no accuracy claim is made. Short histories, missing entries, seasonal changes and unusual busy days may produce misleading results. With no history, a sequence of zeros is not evidence that future revenue will be zero.

Future work could compare predictions with actual outcomes using an error measure and add more historical data. Such evaluation and advanced machine learning are not implemented in the current project.

<!-- PAGE -->
# 9. Testing, Verification and Results

The project uses pytest for automated tests and temporary databases to separate test records from live salon data. pytest supports ordinary assertions, fixtures and temporary-directory testing [6]. Streamlit interaction tests exercise sign-in, role navigation, account creation and dashboard updates.

| Test area | Representative checks |
| --- | --- |
| Models and calculations | Invalid prices and quantities; shares totaling 100%; wage calculations; polymorphic totals. |
| Finance and storage | Payment limits; allowance spending; persistence; exact Decimal report totals. |
| Corrections | Required reasons; invalid allocation rollback; same-day ownership rules; audit persistence. |
| Accounts and interface | Invalid login; session expiry; manager-only operations; cashier wage restrictions; sale/payment dashboard updates. |
| Migrations and analytics | Historical Cash settlement runs once; old records survive; forecast history excludes today and future dates. |

Table 4. Main automated verification areas.

The final review run completed with 367 tests passed. A temporary headless Streamlit server returned HTTP 200 from its health endpoint and was then stopped. Git exclusion checks confirmed that representative database, backup, credential, environment and cache paths are ignored; no sensitive files matching the checked tracked-file patterns were found. The live database was not used for regression tests.

These results support functional correctness for the tested cases. They do not prove production security, forecast accuracy, load capacity or usability for every user. No formal user study or performance benchmark was conducted. Source changes remain local until the tested final version is deliberately published to the repository.

<!-- PAGE -->
# 10. Limitations, Future Work and Conclusion

## 10.1 Limitations

Authentication is basic. The system has no MFA, password recovery screen, account-disable screen or login rate limiting. The first manager setup must be completed before other people can access it. Server and database access must remain restricted.

The audit log is stored inside SQLite and can be changed by someone with direct file access. Product quantity and unit price are used when entering a sale but are not stored separately in the current sales table. Product reports count sale records, not inventory units.

Sale and payment corrections are separate. Although overpayments are rejected, independently changing their amounts can leave a reconciliation difference that a manager must review. Cashier editing eligibility uses the transaction's recorded date, not a separate immutable creation timestamp. Expected wages are not payroll disbursements, and projected margins omit unrecorded costs.

The original src/models classes and integrated transaction classes overlap. They were retained to preserve working coursework examples; future consolidation should avoid maintaining two representations of similar concepts. Forecasts remain unvalidated teaching examples.

## 10.2 Future improvements

Useful extensions are linked sale/payment correction, immutable entry timestamps, inventory control, wage-payment records, stronger account administration, forecast evaluation and automatic receipts. These are proposed improvements, not completed features.

## 10.3 Conclusion

The project meets its main objective of applying Python OOP to a practical salon workflow. It links agreed prices, employee contributions, expected wages, full payments and approved expenses in a persistent application. Abstract transaction and forecast interfaces support inheritance and polymorphism, while validated models demonstrate encapsulation and composition. Automated tests and audited corrections make the calculations easier to review. The system is suitable for demonstrating the coursework concepts while its operational and security limits remain explicit.

<!-- PAGE -->
# References

[1] Streamlit, "Streamlit documentation." Accessed: Nov. 13, 2026. [Online]. Available: https://docs.streamlit.io/

[2] Python Software Foundation, "abc - Abstract Base Classes," Python documentation. Accessed: Nov. 13, 2026. [Online]. Available: https://docs.python.org/3/library/abc.html

[3] Python Software Foundation, "decimal - Decimal fixed-point and floating-point arithmetic," Python documentation. Accessed: Nov. 13, 2026. [Online]. Available: https://docs.python.org/3/library/decimal.html

[4] Python Software Foundation, "hashlib - Secure hashes and message digests," Python documentation. Accessed: Nov. 13, 2026. [Online]. Available: https://docs.python.org/3/library/hashlib.html

[5] Python Software Foundation, "sqlite3 - DB-API 2.0 interface for SQLite databases," Python documentation. Accessed: Nov. 13, 2026. [Online]. Available: https://docs.python.org/3/library/sqlite3.html

[6] pytest developers, "pytest documentation." Accessed: Nov. 13, 2026. [Online]. Available: https://docs.pytest.org/en/stable/
