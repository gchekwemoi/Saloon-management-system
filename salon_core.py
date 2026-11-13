"""Small OOP business layer for the salon coursework prototype.

Data is stored in SQLite; amounts are stored as decimal strings for accuracy.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import sqlite3
from pathlib import Path


def money(value) -> Decimal:
    if isinstance(value, bool):
        raise ValueError('Money must be numeric')
    try:
        result = Decimal(str(value))
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise ValueError('Invalid monetary amount') from exc
    if not result.is_finite():
        raise ValueError('Money must be finite')
    return result


class Transaction(ABC):
    """Abstraction shared by service and retail sales."""
    @abstractmethod
    def calculate_total(self) -> Decimal:
        raise NotImplementedError


@dataclass(frozen=True)
class ServiceTransaction(Transaction):
    agreed_price: Decimal

    def __post_init__(self):
        p = money(self.agreed_price)
        if p <= 0:
            raise ValueError('Service price must be positive')
        object.__setattr__(self, 'agreed_price', p)

    def calculate_total(self) -> Decimal:
        return self.agreed_price


@dataclass(frozen=True)
class ProductTransaction(Transaction):
    quantity: int
    unit_price: Decimal

    def __post_init__(self):
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError('Quantity must be a positive whole number')
        p = money(self.unit_price)
        if p <= 0:
            raise ValueError('Unit price must be positive')
        object.__setattr__(self, 'unit_price', p)

    def calculate_total(self) -> Decimal:
        return self.quantity * self.unit_price


@dataclass(frozen=True)
class Payment:
    amount: Decimal
    method: str
    reference: str = ''

    def __post_init__(self):
        amount = money(self.amount)
        if amount <= 0:
            raise ValueError('Payment amount must be positive')
        if self.method not in ('Cash', 'Mobile Money'):
            raise ValueError('Payment method must be Cash or Mobile Money')
        if self.method == 'Mobile Money' and not self.reference.strip():
            raise ValueError('Mobile Money requires a reference')
        object.__setattr__(self, 'amount', amount)


@dataclass(frozen=True)
class ExpenseAllowance:
    approved_amount: Decimal
    spent_amount: Decimal = Decimal('0')

    def __post_init__(self):
        a, s = money(self.approved_amount), money(self.spent_amount)
        if a < 0 or s < 0 or s > a:
            raise ValueError('Expense must remain within approved allowance')
        object.__setattr__(self, 'approved_amount', a)
        object.__setattr__(self, 'spent_amount', s)

    def remaining_balance(self) -> Decimal:
        return self.approved_amount - self.spent_amount


@dataclass(frozen=True)
class Reconciliation:
    charges: Decimal
    receipts: Decimal
    expenses: Decimal
    expected_wages: Decimal

    def __post_init__(self):
        for field in ('charges', 'receipts', 'expenses', 'expected_wages'):
            v = money(getattr(self, field))
            if v < 0:
                raise ValueError(f'{field} cannot be negative')
            object.__setattr__(self, field, v)

    def unpaid_balance(self) -> Decimal:
        return self.charges - self.receipts

    def net_cash_after_expenses(self) -> Decimal:
        return self.receipts - self.expenses

    def projected_margin_after_wages(self) -> Decimal:
        return self.charges - self.expenses - self.expected_wages


class RevenueForecaster(ABC):
    @abstractmethod
    def forecast(self, daily_totals: list[Decimal], horizon: int = 7) -> list[Decimal]:
        raise NotImplementedError


class MovingAverageForecaster(RevenueForecaster):
    def forecast(self, daily_totals: list[Decimal], horizon: int = 7) -> list[Decimal]:
        if not daily_totals or horizon < 1:
            raise ValueError('Historical revenue and positive horizon required')
        window = daily_totals[-min(7, len(daily_totals)):]
        avg = sum(window, Decimal('0')) / Decimal(len(window))
        return [avg] * horizon


class WeekdayForecaster(RevenueForecaster):
    """Forecast following days using the same weekdays in the last 4 weeks.

    daily_totals must be consecutive, oldest to newest, ending yesterday.
    """
    def forecast(self, daily_totals: list[Decimal], horizon: int = 7) -> list[Decimal]:
        if not daily_totals or horizon < 1:
            raise ValueError('Historical revenue and positive horizon required')
        values = daily_totals[-28:]
        fallback = sum(values, Decimal('0')) / Decimal(len(values))
        estimates = []
        for h in range(horizon):
            # Following days repeat the weekday seen 7, 14, 21 and 28 days before.
            subset = [v for i, v in enumerate(values) if (len(values) - i + h) % 7 == 0]
            estimates.append(sum(subset, Decimal('0')) / len(subset) if subset else fallback)
        return estimates


class SalonDatabase:
    """Persistent records for the classroom demonstration."""
    def __init__(self, path='salon.sqlite3'):
        self.path = str(path)
        self.initialize()

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def initialize(self):
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS employees (
                    employee_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    department TEXT NOT NULL, wage_rate TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS sales (
                    sale_id TEXT PRIMARY KEY, sale_date TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('Service','Product')),
                    description TEXT NOT NULL, amount TEXT NOT NULL,
                    expected_wages TEXT NOT NULL DEFAULT '0');
                CREATE TABLE IF NOT EXISTS assignments (
                    sale_id TEXT NOT NULL REFERENCES sales(sale_id),
                    employee_id TEXT NOT NULL REFERENCES employees(employee_id),
                    share TEXT NOT NULL, wage_rate TEXT NOT NULL,
                    attributed_revenue TEXT NOT NULL, expected_wage TEXT NOT NULL,
                    PRIMARY KEY(sale_id, employee_id));
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id TEXT NOT NULL REFERENCES sales(sale_id),
                    amount TEXT NOT NULL, method TEXT NOT NULL,
                    reference TEXT NOT NULL DEFAULT '', paid_on TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS allowances (
                    allowance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    approved_on TEXT NOT NULL, amount TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '');
                CREATE TABLE IF NOT EXISTS expenses (
                    expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expense_date TEXT NOT NULL, description TEXT NOT NULL,
                    amount TEXT NOT NULL, allowance_id INTEGER NOT NULL
                    REFERENCES allowances(allowance_id));
            ''')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS salon_settings (
                    setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS cashiers (
                    cashier_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1);
            ''')
            # Safe migration: keep all existing sales, payments and expenses.
            for table in ('sales', 'payments', 'expenses'):
                columns = {row['name'] for row in db.execute(f'PRAGMA table_info({table})')}
                if 'cashier_id' not in columns:
                    db.execute(f'ALTER TABLE {table} ADD COLUMN cashier_id TEXT REFERENCES cashiers(cashier_id)')

    def salon_name(self):
        with self.connect() as db:
            row = db.execute('SELECT setting_value FROM salon_settings WHERE setting_key=?', ('salon_name',)).fetchone()
            return row['setting_value'] if row else 'Saloon Management System'

    def set_salon_name(self, name):
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Salon name is required')
        with self.connect() as db:
            db.execute('INSERT INTO salon_settings (setting_key, setting_value) VALUES (?, ?) '
                       'ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value',
                       ('salon_name', name.strip()))

    def add_cashier(self, cashier_id, name):
        if not all(isinstance(x, str) and x.strip() for x in (cashier_id, name)):
            raise ValueError('Cashier ID and name are required')
        with self.connect() as db:
            db.execute('INSERT INTO cashiers (cashier_id, name, active) VALUES (?, ?, 1)',
                       (cashier_id.strip(), name.strip()))

    def cashiers(self, active_only=False):
        with self.connect() as db:
            query = 'SELECT * FROM cashiers' + (' WHERE active=1' if active_only else '') + ' ORDER BY name'
            return [dict(row) for row in db.execute(query)]

    def cashier_name(self, cashier_id):
        if not cashier_id:
            return 'Not recorded'
        with self.connect() as db:
            row = db.execute('SELECT name FROM cashiers WHERE cashier_id=?', (cashier_id,)).fetchone()
            return row['name'] if row else 'Unknown cashier'

    def _check_cashier(self, cashier_id):
        if cashier_id is None:
            return  # Backward compatible with previous coursework tests.
        if not isinstance(cashier_id, str) or not cashier_id.strip():
            raise ValueError('Select a cashier')
        with self.connect() as db:
            row = db.execute('SELECT active FROM cashiers WHERE cashier_id=?', (cashier_id,)).fetchone()
            if row is None or not row['active']:
                raise ValueError('Select a registered, active cashier')

    def add_employee(self, employee_id, name, department, wage_rate):
        if not all(isinstance(v, str) and v.strip() for v in (employee_id, name, department)):
            raise ValueError('Employee ID, name and department are required')
        r = money(wage_rate)
        if not (0 <= r <= 100):
            raise ValueError('Wage rate must be between 0 and 100')
        with self.connect() as db:
            db.execute('INSERT INTO employees VALUES (?,?,?,?,1)', (employee_id.strip(), name.strip(), department.strip(), str(r)))

    def employees(self, active_only=False):
        with self.connect() as db:
            query = 'SELECT * FROM employees' + (' WHERE active=1' if active_only else '') + ' ORDER BY name'
            return [dict(row) for row in db.execute(query)]

    def record_sale(self, sale_id, sale_date, kind, description, transaction: Transaction, assignments=None, cashier_id=None):
        if not all(isinstance(v, str) and v.strip() for v in (sale_id, description)):
            raise ValueError('Sale ID and description are required')
        if not isinstance(sale_date, date):
            raise ValueError('Sale date required')
        if kind not in ('Service', 'Product') or not isinstance(transaction, Transaction):
            raise ValueError('Invalid sale type')
        self._check_cashier(cashier_id)
        assignments = assignments or []
        if kind == 'Service' and not assignments:
            raise ValueError('Service sales require employee assignments')
        if kind == 'Product' and assignments:
            raise ValueError('Products do not use service employee assignments')
        total = transaction.calculate_total()
        wages = Decimal('0')
        records = []
        if assignments:
            seen = set()
            shares = Decimal('0')
            known = {x['employee_id']: x for x in self.employees(active_only=True)}
            for eid, share in assignments:
                if eid in seen or eid not in known:
                    raise ValueError('Duplicate or inactive/unknown employee')
                seen.add(eid)
                share = money(share)
                rate = money(known[eid]['wage_rate'])
                if not (0 < share <= 100):
                    raise ValueError('Invalid employee share')
                revenue = total * share / Decimal('100')
                wage = revenue * rate / Decimal('100')
                records.append((sale_id, eid, str(share), str(rate), str(revenue), str(wage)))
                shares += share
                wages += wage
            if shares != 100:
                raise ValueError('Employee contributions must total exactly 100%')
        with self.connect() as db:
            db.execute('INSERT INTO sales (sale_id, sale_date, kind, description, amount, expected_wages, cashier_id) VALUES (?,?,?,?,?,?,?)',
                       (sale_id.strip(), sale_date.isoformat(), kind, description.strip(), str(total), str(wages), cashier_id))
            db.executemany('INSERT INTO assignments VALUES (?,?,?,?,?,?)', records)
        return total

    def sales(self):
        with self.connect() as db:
            return [dict(x) for x in db.execute('''SELECT s.*, COALESCE(c.name,'Not recorded') AS cashier_name
                 FROM sales s LEFT JOIN cashiers c ON c.cashier_id=s.cashier_id
                 ORDER BY s.sale_date DESC, s.sale_id DESC''')]

    def add_payment(self, sale_id, payment: Payment, paid_on=None, cashier_id=None):
        self._check_cashier(cashier_id)
        paid_on = paid_on or date.today()
        with self.connect() as db:
            row = db.execute('SELECT amount FROM sales WHERE sale_id=?', (sale_id,)).fetchone()
            if row is None:
                raise ValueError('Unknown sale')
            paid = sum((money(x[0]) for x in db.execute('SELECT amount FROM payments WHERE sale_id=?', (sale_id,))), Decimal('0'))
            if paid + payment.amount > money(row['amount']):
                raise ValueError('Payment exceeds outstanding balance')
            db.execute('INSERT INTO payments (sale_id, amount, method, reference, paid_on, cashier_id) VALUES (?,?,?,?,?,?)',
                       (sale_id, str(payment.amount), payment.method, payment.reference, paid_on.isoformat(), cashier_id))

    def allowances(self):
        with self.connect() as db:
            return [dict(x) for x in db.execute('SELECT * FROM allowances ORDER BY allowance_id DESC')]

    def payments(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('''
                SELECT p.*, COALESCE(c.name, 'Not recorded') AS cashier_name
                FROM payments p LEFT JOIN cashiers c ON c.cashier_id=p.cashier_id
                ORDER BY p.paid_on DESC, p.payment_id DESC''')]

    def expenses(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('''
                SELECT e.*, COALESCE(c.name, 'Not recorded') AS cashier_name
                FROM expenses e LEFT JOIN cashiers c ON c.cashier_id=e.cashier_id
                ORDER BY e.expense_date DESC, e.expense_id DESC''')]

    def approve_allowance(self, amount, note=''):
        amount = money(amount)
        if amount <= 0:
            raise ValueError('Allowance must be positive')
        with self.connect() as db:
            db.execute('INSERT INTO allowances (approved_on,amount,note) VALUES (?,?,?)',
                       (date.today().isoformat(), str(amount), note))

    def remaining_allowance(self, allowance_id):
        with self.connect() as db:
            row = db.execute('SELECT amount FROM allowances WHERE allowance_id=?', (allowance_id,)).fetchone()
            if row is None:
                raise ValueError('Unknown allowance')
            spent = sum((money(x[0]) for x in db.execute('SELECT amount FROM expenses WHERE allowance_id=?', (allowance_id,))), Decimal('0'))
            return ExpenseAllowance(money(row['amount']), spent).remaining_balance()

    def add_expense(self, allowance_id, description, amount, cashier_id=None):
        self._check_cashier(cashier_id)
        if not isinstance(description, str) or not description.strip():
            raise ValueError('Expense description required')
        amount = money(amount)
        if amount <= 0 or amount > self.remaining_allowance(allowance_id):
            raise ValueError('Expense must be positive and within remaining allowance')
        with self.connect() as db:
            db.execute('INSERT INTO expenses (expense_date,description,amount,allowance_id,cashier_id) VALUES (?,?,?,?,?)',
                       (date.today().isoformat(), description.strip(), str(amount), allowance_id, cashier_id))

    def summary(self):
        with self.connect() as db:
            charges = sum((money(x[0]) for x in db.execute('SELECT amount FROM sales')), Decimal('0'))
            wages = sum((money(x[0]) for x in db.execute('SELECT expected_wages FROM sales')), Decimal('0'))
            receipts = sum((money(x[0]) for x in db.execute('SELECT amount FROM payments')), Decimal('0'))
            expenses = sum((money(x[0]) for x in db.execute('SELECT amount FROM expenses')), Decimal('0'))
        return Reconciliation(charges, receipts, expenses, wages)

    def daily_revenue(self, days=28):
        end = date.today()
        start = end - timedelta(days=days-1)
        with self.connect() as db:
            data = {}
            for row in db.execute('SELECT sale_date, amount FROM sales WHERE sale_date>=?',
                                  (start.isoformat(),)):
                key = row['sale_date']
                data[key] = data.get(key, Decimal('0')) + money(row['amount'])
        return [(start + timedelta(days=i), data.get((start + timedelta(days=i)).isoformat(), Decimal('0'))) for i in range(days)]

    def productivity(self):
        with self.connect() as db:
            return [dict(x) for x in db.execute('''
              SELECT e.name, e.department,
              COUNT(a.sale_id) AS jobs,
              SUM(CAST(a.attributed_revenue AS REAL)) AS revenue,
              SUM(CAST(a.expected_wage AS REAL)) AS expected_wages
              FROM assignments a JOIN employees e ON a.employee_id=e.employee_id
              GROUP BY e.employee_id ORDER BY revenue DESC''')]

    def cashier_activity(self):
        with self.connect() as db:
            return [dict(x) for x in db.execute('''
                SELECT c.cashier_id, c.name,
                  (SELECT COUNT(*) FROM sales s WHERE s.cashier_id=c.cashier_id) AS sales_count,
                  (SELECT COALESCE(SUM(CAST(s.amount AS REAL)),0) FROM sales s WHERE s.cashier_id=c.cashier_id) AS charges,
                  (SELECT COALESCE(SUM(CAST(p.amount AS REAL)),0) FROM payments p WHERE p.cashier_id=c.cashier_id) AS receipts,
                  (SELECT COUNT(*) FROM payments p WHERE p.cashier_id=c.cashier_id) AS payment_count,
                  (SELECT COALESCE(SUM(CAST(e.amount AS REAL)),0) FROM expenses e WHERE e.cashier_id=c.cashier_id) AS expenses
                FROM cashiers c ORDER BY c.name''')]
