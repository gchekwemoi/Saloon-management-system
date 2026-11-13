"""Small OOP business layer for the salon coursework prototype.

Data is stored in SQLite; amounts are stored as decimal strings for accuracy.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import sqlite3
import hashlib
import hmac
import secrets
import json
import time


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
        self.session_token = None
        self.initialize()
        self.settle_legacy_cash_balances()

    def settle_legacy_cash_balances(self):
        """One-time, user-authorized reconciliation of historical unpaid sales."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)')
            name = 'legacy_outstanding_as_cash_v1'
            if db.execute('SELECT 1 FROM schema_migrations WHERE name=?', (name,)).fetchone():
                return
            now = datetime.now(timezone.utc).isoformat()
            for sale in db.execute('SELECT * FROM sales').fetchall():
                paid = sum((money(row[0]) for row in db.execute('SELECT amount FROM payments WHERE sale_id=?', (sale['sale_id'],))), Decimal(0))
                balance = money(sale['amount']) - paid
                if balance < 0:
                    raise ValueError('Historical overpayment detected; cash reconciliation rolled back')
                if balance == 0:
                    continue
                cursor = db.execute('''INSERT INTO payments
                    (sale_id,amount,method,reference,paid_on,cashier_id) VALUES (?,?,?,?,?,?)''',
                    (sale['sale_id'], str(balance), 'Cash', 'Legacy balance settled as Cash', sale['sale_date'], sale['cashier_id']))
                payment = dict(db.execute('SELECT * FROM payments WHERE payment_id=?', (cursor.lastrowid,)).fetchone())
                db.execute('''INSERT INTO correction_audit
                    (entity,record_id,previous_values,corrected_values,reason,corrected_at,username)
                    VALUES (?,?,?,?,?,?,?)''', ('payments', str(cursor.lastrowid), '{}', json.dumps(payment),
                    'User-authorized migration: settle existing unpaid balance as Cash', now, 'system:migration'))
            db.execute('INSERT INTO schema_migrations VALUES (?,?)', (name, now))

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def has_accounts(self):
        with self.connect() as db:
            return db.execute('SELECT 1 FROM accounts LIMIT 1').fetchone() is not None

    @staticmethod
    def _password_hash(password, salt=None):
        if not isinstance(password, str) or len(password) < 12:
            raise ValueError('Use a password of at least 12 characters')
        salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
        return salt + ':' + digest

    def setup_manager(self, username, password):
        encoded = self._password_hash(password)
        if not username.strip():
            raise ValueError('Username required')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM accounts LIMIT 1').fetchone():
                raise PermissionError('Initial setup has already been completed')
            db.execute('INSERT INTO accounts VALUES (?,?,?,NULL)', (username.strip(), encoded, 'Owner/Manager'))

    def create_account(self, username, password, role, cashier_id=None):
        self.require_manager()
        if role not in ('Owner/Manager', 'Cashier') or not username.strip():
            raise ValueError('Valid username and role required')
        if role == 'Cashier':
            if not cashier_id:
                raise ValueError('Cashier account must be linked to a registered cashier')
            self._check_cashier(cashier_id)
        with self.connect() as db:
            db.execute('INSERT INTO accounts VALUES (?,?,?,?)',
                       (username.strip(), self._password_hash(password), role, cashier_id))

    def login(self, username, password):
        with self.connect() as db:
            row = db.execute('SELECT * FROM accounts WHERE username=?', (username.strip(),)).fetchone()
            encoded = row['password_hash'] if row else self._password_hash('dummy-password-value', '00' * 16)
            salt = encoded.split(':')[0]
            candidate = self._password_hash(password, salt) if len(password) >= 12 else self._password_hash('dummy-password-value', salt)
            if row is None or len(password) < 12 or not hmac.compare_digest(candidate, encoded):
                raise PermissionError('Invalid username or password')
            token = secrets.token_urlsafe(32)
            db.execute('INSERT INTO sessions VALUES (?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(), row['username'], time.time() + 8 * 3600))
        self.session_token = token
        return token

    def current_user(self):
        if not self.session_token:
            raise PermissionError('Sign in required')
        with self.connect() as db:
            row = db.execute('''SELECT a.username,a.role,a.cashier_id FROM sessions s
                JOIN accounts a ON a.username=s.username WHERE token_hash=? AND expires_at>?''',
                (hashlib.sha256(self.session_token.encode()).hexdigest(), time.time())).fetchone()
            if row is None:
                raise PermissionError('Session expired; sign in again')
            if row['role'] == 'Cashier':
                self._check_cashier(row['cashier_id'])
            return dict(row)

    def require_manager(self):
        user = self.current_user()
        if user['role'] != 'Owner/Manager':
            raise PermissionError('Owner/Manager permission required')
        return user

    def _recording_cashier(self, cashier_id):
        user = self.current_user()
        if user['role'] == 'Cashier':
            if cashier_id is not None and cashier_id != user['cashier_id']:
                raise PermissionError('Cannot record as another cashier')
            return user['cashier_id']
        return cashier_id

    def cashier_dashboard(self):
        """Operational totals for this cashier's sales; never include payroll."""
        user = self.current_user()
        if user['role'] != 'Cashier':
            raise PermissionError('Cashier account required')
        with self.connect() as db:
            db.execute('BEGIN')
            charges = sum((money(x[0]) for x in db.execute(
                'SELECT amount FROM sales WHERE cashier_id=?', (user['cashier_id'],))), Decimal(0))
            sale_receipts = sum((money(x[0]) for x in db.execute('''SELECT p.amount FROM payments p
                JOIN sales s ON s.sale_id=p.sale_id WHERE s.cashier_id=?''', (user['cashier_id'],))), Decimal(0))
            receipts = sum((money(x[0]) for x in db.execute(
                'SELECT amount FROM payments WHERE cashier_id=?', (user['cashier_id'],))), Decimal(0))
        return {'charges': charges, 'receipts': receipts, 'outstanding': charges - sale_receipts}

    def cashier_collection_dashboard(self):
        """Cash and Mobile Money collected against this cashier's sales."""
        user = self.current_user()
        if user['role'] != 'Cashier':
            raise PermissionError('Cashier account required')
        totals = {'Cash': Decimal(0), 'Mobile Money': Decimal(0)}
        with self.connect() as db:
            for row in db.execute('''SELECT p.amount,p.method FROM payments p
                JOIN sales s ON s.sale_id=p.sale_id WHERE s.cashier_id=?''', (user['cashier_id'],)):
                totals[row['method']] += money(row['amount'])
        return {'collected': sum(totals.values(), Decimal(0)), 'cash': totals['Cash'], 'mobile_money': totals['Mobile Money']}

    def operating_activity(self):
        """Product and expense registers scoped to the authenticated role."""
        user = self.current_user()
        with self.connect() as db:
            db.execute('BEGIN')
            scope = ' AND s.cashier_id=?' if user['role'] == 'Cashier' else ''
            params = (user['cashier_id'],) if scope else ()
            products = [dict(row) for row in db.execute('''
                SELECT s.sale_id,s.sale_date,s.description,s.amount,s.cashier_id,
                       COALESCE(c.name,'Not recorded') AS cashier_name
                FROM sales s LEFT JOIN cashiers c ON c.cashier_id=s.cashier_id
                WHERE s.kind='Product' ''' + scope + ' ORDER BY s.sale_date DESC,s.sale_id DESC', params)]
            scope = ' WHERE e.cashier_id=?' if user['role'] == 'Cashier' else ''
            expenses = [dict(row) for row in db.execute('''
                SELECT e.*,COALESCE(c.name,'Not recorded') AS cashier_name
                FROM expenses e LEFT JOIN cashiers c ON c.cashier_id=e.cashier_id
                ''' + scope + ' ORDER BY e.expense_date DESC,e.expense_id DESC', params)]
        return {'products': products, 'expenses': expenses,
                'product_total': sum((money(row['amount']) for row in products), Decimal(0)),
                'expense_total': sum((money(row['amount']) for row in expenses), Decimal(0))}

    def logout(self):
        with self.connect() as db:
            if self.session_token:
                db.execute('DELETE FROM sessions WHERE token_hash=?',
                           (hashlib.sha256(self.session_token.encode()).hexdigest(),))
        self.session_token = None

    def assignments_for_sale(self, sale_id):
        self.require_manager()
        with self.connect() as db:
            return [dict(x) for x in db.execute('SELECT * FROM assignments WHERE sale_id=?', (sale_id,))]

    def audit_log(self):
        self.require_manager()
        with self.connect() as db:
            return [dict(x) for x in db.execute('SELECT * FROM correction_audit ORDER BY audit_id DESC')]

    def cashier_editable_records(self, entity):
        user = self.current_user()
        if user['role'] != 'Cashier' or entity not in ('sales', 'payments', 'expenses'):
            raise PermissionError('Cashier register required')
        date_field = {'sales': 'sale_date', 'payments': 'paid_on', 'expenses': 'expense_date'}[entity]
        today = datetime.now(timezone(timedelta(hours=3))).date().isoformat()
        with self.connect() as db:
            rows = [dict(row) for row in db.execute(
                f'SELECT * FROM {entity} WHERE cashier_id=? AND {date_field}=?', (user['cashier_id'], today))]
        return [{k: v for k, v in row.items() if k != 'expected_wages'} for row in rows]

    def correct_transaction(self, entity, record_id, changes, reason):
        """Validate, replace and audit a correction under one SQLite write lock."""
        user = self.current_user()
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError('A correction reason is required')
        keys = {'sales': 'sale_id', 'payments': 'payment_id', 'expenses': 'expense_id'}
        allowed = {'sales': {'description', 'amount', 'sale_date', 'cashier_id', 'assignments'},
                   'payments': {'sale_id', 'amount', 'method', 'reference', 'paid_on', 'cashier_id'},
                   'expenses': {'description', 'amount', 'expense_date', 'allowance_id', 'cashier_id'}}
        if entity not in keys or not changes or set(changes) - allowed[entity]:
            raise ValueError('Invalid correction fields')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            key = keys[entity]
            row = db.execute(f'SELECT * FROM {entity} WHERE {key}=?', (record_id,)).fetchone()
            if row is None:
                raise ValueError('Record not found')
            previous = dict(row)
            if user['role'] == 'Cashier':
                today = datetime.now(timezone(timedelta(hours=3))).date().isoformat()
                date_field = {'sales': 'sale_date', 'payments': 'paid_on', 'expenses': 'expense_date'}[entity]
                if previous['cashier_id'] != user['cashier_id'] or previous[date_field] != today:
                    raise PermissionError('Cashiers can edit only their own transactions dated today (Kampala time)')
                restricted = {'cashier_id', 'sale_date', 'paid_on', 'expense_date', 'assignments', 'sale_id', 'allowance_id'}
                if set(changes) & restricted:
                    raise PermissionError('Cashiers cannot change dates, cashier, allocations, sale links or allowances')
            updated = dict(previous)
            updated.update({k: v for k, v in changes.items() if k != 'assignments'})
            amount = money(updated['amount'])
            if amount <= 0:
                raise ValueError('Amount must be positive')
            updated['amount'] = str(amount)
            if not updated.get('description', 'valid').strip():
                raise ValueError('Description required')
            date_key = {'sales': 'sale_date', 'payments': 'paid_on', 'expenses': 'expense_date'}[entity]
            date.fromisoformat(updated[date_key])
            cid = updated['cashier_id']
            if cid is not None and not db.execute('SELECT 1 FROM cashiers WHERE cashier_id=?', (cid,)).fetchone():
                raise ValueError('Unknown cashier')
            if entity == 'sales':
                old_assignments = [dict(x) for x in db.execute('SELECT * FROM assignments WHERE sale_id=?', (record_id,))]
                previous['assignments'] = old_assignments
                allocation = changes.get('assignments', [(x['employee_id'], x['share']) for x in old_assignments])
                if (updated['kind'] == 'Product' and allocation) or (updated['kind'] == 'Service' and not allocation):
                    raise ValueError('Invalid employee allocation for sale type')
                records, seen, shares, wages = [], set(), Decimal(0), Decimal(0)
                historic = {x['employee_id']: x['wage_rate'] for x in old_assignments}
                for eid, share in allocation:
                    employee = db.execute('SELECT * FROM employees WHERE employee_id=?', (eid,)).fetchone()
                    if eid in seen or employee is None or (not employee['active'] and eid not in historic):
                        raise ValueError('Duplicate or unknown/inactive employee')
                    seen.add(eid)
                    share = money(share)
                    if not 0 < share <= 100:
                        raise ValueError('Invalid employee share')
                    rate = money(historic.get(eid, employee['wage_rate']))
                    revenue = amount * share / 100
                    wage = revenue * rate / 100
                    shares += share
                    wages += wage
                    records.append((record_id, eid, str(share), str(rate), str(revenue), str(wage)))
                if allocation and shares != 100:
                    raise ValueError('Employee contributions must total exactly 100%')
                paid = sum((money(x[0]) for x in db.execute('SELECT amount FROM payments WHERE sale_id=?', (record_id,))), Decimal(0))
                if paid > amount:
                    raise ValueError('Correction would overpay the sale')
                updated['expected_wages'] = str(wages)
                db.execute('DELETE FROM assignments WHERE sale_id=?', (record_id,))
                db.executemany('INSERT INTO assignments VALUES (?,?,?,?,?,?)', records)
            elif entity == 'payments':
                Payment(amount, updated['method'], updated['reference'])
                sale = db.execute('SELECT amount FROM sales WHERE sale_id=?', (updated['sale_id'],)).fetchone()
                paid = sum((money(x[0]) for x in db.execute('SELECT amount FROM payments WHERE sale_id=? AND payment_id<>?', (updated['sale_id'], record_id))), Decimal(0))
                if sale is None or paid + amount > money(sale[0]):
                    raise ValueError('Unknown sale or payment exceeds outstanding balance')
            else:
                allowance = db.execute('SELECT amount FROM allowances WHERE allowance_id=?', (updated['allowance_id'],)).fetchone()
                spent = sum((money(x[0]) for x in db.execute('SELECT amount FROM expenses WHERE allowance_id=? AND expense_id<>?', (updated['allowance_id'], record_id))), Decimal(0))
                if allowance is None or spent + amount > money(allowance[0]):
                    raise ValueError('Expense exceeds allowance')
            fields = [k for k in updated if k != key]
            db.execute(f'UPDATE {entity} SET ' + ','.join(f'{k}=?' for k in fields) + f' WHERE {key}=?',
                       [updated[k] for k in fields] + [record_id])
            if entity == 'sales':
                updated['assignments'] = [dict(x) for x in db.execute('SELECT * FROM assignments WHERE sale_id=?', (record_id,))]
            db.execute('''INSERT INTO correction_audit
                (entity,record_id,previous_values,corrected_values,reason,corrected_at,username) VALUES (?,?,?,?,?,?,?)''',
                (entity, str(record_id), json.dumps(previous), json.dumps(updated), reason.strip(),
                 datetime.now(timezone.utc).isoformat(), user['username']))

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
                CREATE TABLE IF NOT EXISTS accounts (
                    username TEXT PRIMARY KEY, password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('Owner/Manager','Cashier')),
                    cashier_id TEXT REFERENCES cashiers(cashier_id));
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, username TEXT NOT NULL REFERENCES accounts(username),
                    expires_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS correction_audit (
                    audit_id INTEGER PRIMARY KEY, entity TEXT NOT NULL, record_id TEXT NOT NULL,
                    previous_values TEXT NOT NULL, corrected_values TEXT NOT NULL,
                    reason TEXT NOT NULL, corrected_at TEXT NOT NULL, username TEXT NOT NULL);
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
        self.require_manager()
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Salon name is required')
        with self.connect() as db:
            db.execute('INSERT INTO salon_settings (setting_key, setting_value) VALUES (?, ?) '
                       'ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value',
                       ('salon_name', name.strip()))

    def add_cashier(self, cashier_id, name):
        self.require_manager()
        if not all(isinstance(x, str) and x.strip() for x in (cashier_id, name)):
            raise ValueError('Cashier ID and name are required')
        with self.connect() as db:
            db.execute('INSERT INTO cashiers (cashier_id, name, active) VALUES (?, ?, 1)',
                       (cashier_id.strip(), name.strip()))

    def cashiers(self, active_only=False):
        self.require_manager()
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
        self.require_manager()
        if not all(isinstance(v, str) and v.strip() for v in (employee_id, name, department)):
            raise ValueError('Employee ID, name and department are required')
        r = money(wage_rate)
        if not (0 <= r <= 100):
            raise ValueError('Wage rate must be between 0 and 100')
        with self.connect() as db:
            db.execute('INSERT INTO employees VALUES (?,?,?,?,1)', (employee_id.strip(), name.strip(), department.strip(), str(r)))

    def employees(self, active_only=False):
        user = self.current_user()
        with self.connect() as db:
            query = 'SELECT * FROM employees' + (' WHERE active=1' if active_only else '') + ' ORDER BY name'
            rows = [dict(row) for row in db.execute(query)]
            if user['role'] == 'Cashier':
                for row in rows:
                    row.pop('wage_rate', None)
            return rows

    def record_sale(self, sale_id, sale_date, kind, description, transaction: Transaction, assignments=None, cashier_id=None, payment=None):
        cashier_id = self._recording_cashier(cashier_id)
        if not all(isinstance(v, str) and v.strip() for v in (sale_id, description)):
            raise ValueError('Sale ID and description are required')
        if not isinstance(sale_date, date) or isinstance(sale_date, datetime):
            raise ValueError('Sale date required')
        if kind not in ('Service', 'Product') or not isinstance(transaction, Transaction):
            raise ValueError('Invalid sale type')
        if (kind == 'Service' and not isinstance(transaction, ServiceTransaction)) or (
                kind == 'Product' and not isinstance(transaction, ProductTransaction)):
            raise ValueError('Transaction must match the sale type')
        self._check_cashier(cashier_id)
        assignments = assignments or []
        if kind == 'Service' and not assignments:
            raise ValueError('Service sales require employee assignments')
        if kind == 'Product' and assignments:
            raise ValueError('Products do not use service employee assignments')
        total = transaction.calculate_total()
        if payment is not None and (not isinstance(payment, Payment) or payment.amount != total):
            raise ValueError('Sale payment must equal the full sale amount')
        wages = Decimal('0')
        records = []
        if assignments:
            seen = set()
            shares = Decimal('0')
            with self.connect() as db:
                known = {x['employee_id']: dict(x) for x in db.execute('SELECT * FROM employees WHERE active=1')}
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
            if payment is not None:
                db.execute('INSERT INTO payments (sale_id,amount,method,reference,paid_on,cashier_id) VALUES (?,?,?,?,?,?)',
                           (sale_id.strip(), str(payment.amount), payment.method, payment.reference, sale_date.isoformat(), cashier_id))
        return total

    def sales(self):
        user = self.current_user()
        with self.connect() as db:
            rows = [dict(x) for x in db.execute('''SELECT s.*, COALESCE(c.name,'Not recorded') AS cashier_name,
                 COALESCE((SELECT GROUP_CONCAT(worker, ', ') FROM (
                     SELECT e.name || ' (' || e.employee_id || ')' AS worker
                     FROM assignments a JOIN employees e ON e.employee_id=a.employee_id
                     WHERE a.sale_id=s.sale_id ORDER BY e.name,e.employee_id
                 )), CASE WHEN s.kind='Product' THEN 'Not applicable' ELSE 'Not recorded' END) AS service_employees
                 FROM sales s LEFT JOIN cashiers c ON c.cashier_id=s.cashier_id
                 ORDER BY s.sale_date DESC, s.sale_id DESC''')]
            if user['role'] == 'Cashier':
                for row in rows:
                    row.pop('expected_wages', None)
            return rows

    def record_paid_sale(self, *args, payment, **kwargs):
        if not isinstance(payment, Payment):
            raise ValueError('Full payment is required with a new sale')
        return self.record_sale(*args, payment=payment, **kwargs)

    def add_payment(self, sale_id, payment: Payment, paid_on=None, cashier_id=None):
        cashier_id = self._recording_cashier(cashier_id)
        self._check_cashier(cashier_id)
        paid_on = paid_on or date.today()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT amount FROM sales WHERE sale_id=?', (sale_id,)).fetchone()
            if row is None:
                raise ValueError('Unknown sale')
            paid = sum((money(x[0]) for x in db.execute('SELECT amount FROM payments WHERE sale_id=?', (sale_id,))), Decimal('0'))
            if paid + payment.amount > money(row['amount']):
                raise ValueError('Payment exceeds outstanding balance')
            db.execute('INSERT INTO payments (sale_id, amount, method, reference, paid_on, cashier_id) VALUES (?,?,?,?,?,?)',
                       (sale_id, str(payment.amount), payment.method, payment.reference, paid_on.isoformat(), cashier_id))

    def allowances(self):
        self.current_user()
        with self.connect() as db:
            return [dict(x) for x in db.execute('SELECT * FROM allowances ORDER BY allowance_id DESC')]

    def payments(self):
        self.require_manager()
        with self.connect() as db:
            return [dict(row) for row in db.execute('''
                SELECT p.*, COALESCE(c.name, 'Not recorded') AS cashier_name
                FROM payments p LEFT JOIN cashiers c ON c.cashier_id=p.cashier_id
                ORDER BY p.paid_on DESC, p.payment_id DESC''')]

    def expenses(self):
        self.require_manager()
        with self.connect() as db:
            return [dict(row) for row in db.execute('''
                SELECT e.*, COALESCE(c.name, 'Not recorded') AS cashier_name
                FROM expenses e LEFT JOIN cashiers c ON c.cashier_id=e.cashier_id
                ORDER BY e.expense_date DESC, e.expense_id DESC''')]

    def approve_allowance(self, amount, note=''):
        self.require_manager()
        amount = money(amount)
        if amount <= 0:
            raise ValueError('Allowance must be positive')
        with self.connect() as db:
            db.execute('INSERT INTO allowances (approved_on,amount,note) VALUES (?,?,?)',
                       (date.today().isoformat(), str(amount), note))

    def remaining_allowance(self, allowance_id):
        self.current_user()
        with self.connect() as db:
            row = db.execute('SELECT amount FROM allowances WHERE allowance_id=?', (allowance_id,)).fetchone()
            if row is None:
                raise ValueError('Unknown allowance')
            spent = sum((money(x[0]) for x in db.execute('SELECT amount FROM expenses WHERE allowance_id=?', (allowance_id,))), Decimal('0'))
            return ExpenseAllowance(money(row['amount']), spent).remaining_balance()

    def add_expense(self, allowance_id, description, amount, cashier_id=None):
        cashier_id = self._recording_cashier(cashier_id)
        self._check_cashier(cashier_id)
        if not isinstance(description, str) or not description.strip():
            raise ValueError('Expense description required')
        amount = money(amount)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            allowance = db.execute('SELECT amount FROM allowances WHERE allowance_id=?', (allowance_id,)).fetchone()
            spent = sum((money(x[0]) for x in db.execute('SELECT amount FROM expenses WHERE allowance_id=?', (allowance_id,))), Decimal(0))
            if allowance is None or amount <= 0 or spent + amount > money(allowance[0]):
                raise ValueError('Expense must be positive and within remaining allowance')
            db.execute('INSERT INTO expenses (expense_date,description,amount,allowance_id,cashier_id) VALUES (?,?,?,?,?)',
                       (date.today().isoformat(), description.strip(), str(amount), allowance_id, cashier_id))

    def summary(self):
        self.require_manager()
        with self.connect() as db:
            charges = sum((money(x[0]) for x in db.execute('SELECT amount FROM sales')), Decimal('0'))
            wages = sum((money(x[0]) for x in db.execute('SELECT expected_wages FROM sales')), Decimal('0'))
            receipts = sum((money(x[0]) for x in db.execute('SELECT amount FROM payments')), Decimal('0'))
            expenses = sum((money(x[0]) for x in db.execute('SELECT amount FROM expenses')), Decimal('0'))
        return Reconciliation(charges, receipts, expenses, wages)

    def daily_revenue(self, days=28):
        self.require_manager()
        if type(days) is not int or days < 1:
            raise ValueError('History length must be a positive whole number')
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=days-1)
        with self.connect() as db:
            data = {}
            for row in db.execute('SELECT sale_date, amount FROM sales WHERE sale_date BETWEEN ? AND ?',
                                  (start.isoformat(), end.isoformat())):
                key = row['sale_date']
                data[key] = data.get(key, Decimal('0')) + money(row['amount'])
        return [(start + timedelta(days=i), data.get((start + timedelta(days=i)).isoformat(), Decimal('0'))) for i in range(days)]

    def productivity(self):
        self.require_manager()
        totals = {}
        with self.connect() as db:
            rows = db.execute("""SELECT e.employee_id,e.name,e.department,
                a.attributed_revenue,a.expected_wage FROM assignments a
                JOIN employees e ON e.employee_id=a.employee_id""")
            for row in rows:
                employee_id = row['employee_id']
                if employee_id not in totals:
                    totals[employee_id] = {'name': row['name'], 'department': row['department'],
                                           'jobs': 0, 'revenue': Decimal(0), 'expected_wages': Decimal(0)}
                employee = totals[employee_id]
                employee['jobs'] += 1
                employee['revenue'] += money(row['attributed_revenue'])
                employee['expected_wages'] += money(row['expected_wage'])
        return sorted(totals.values(), key=lambda employee: employee['revenue'], reverse=True)

    def report_records(self, report, start, end, cashier_id=None, sale_kind=None, payment_method=None):
        """Return manager-only report rows with inclusive transaction dates."""
        self.require_manager()
        if type(start) is not date or type(end) is not date or start > end:
            raise ValueError('Choose a valid start and end date')
        if report not in ('Sales', 'Payments', 'Expenses', 'Employee allocations'):
            raise ValueError('Unknown report')
        if sale_kind not in (None, 'Service', 'Product') or payment_method not in (None, 'Cash', 'Mobile Money'):
            raise ValueError('Invalid report filter')
        if payment_method and report != 'Payments':
            raise ValueError('Payment method applies only to payment reports')
        if sale_kind and report == 'Expenses':
            raise ValueError('Sale type does not apply to expenses')
        queries = {
            'Sales': ('''SELECT s.sale_date AS date,s.sale_id,s.kind,s.description,s.amount,
                        s.expected_wages,s.cashier_id,COALESCE(c.name,'Not recorded') AS cashier_name
                        FROM sales s LEFT JOIN cashiers c ON c.cashier_id=s.cashier_id''', 's.sale_date', 's.cashier_id'),
            'Payments': ('''SELECT p.paid_on AS date,p.payment_id,p.sale_id,s.kind,p.amount,
                        p.method,p.reference,p.cashier_id,COALESCE(c.name,'Not recorded') AS cashier_name
                        FROM payments p JOIN sales s ON s.sale_id=p.sale_id
                        LEFT JOIN cashiers c ON c.cashier_id=p.cashier_id''', 'p.paid_on', 'p.cashier_id'),
            'Expenses': ('''SELECT e.expense_date AS date,e.expense_id,e.description,e.amount,
                        e.allowance_id,e.cashier_id,COALESCE(c.name,'Not recorded') AS cashier_name
                        FROM expenses e LEFT JOIN cashiers c ON c.cashier_id=e.cashier_id''', 'e.expense_date', 'e.cashier_id'),
            'Employee allocations': ('''SELECT s.sale_date AS date,s.sale_id,a.employee_id,
                        e.name AS employee_name,e.department,a.share,a.wage_rate,
                        a.attributed_revenue AS amount,a.expected_wage AS expected_wages,
                        s.cashier_id,COALESCE(c.name,'Not recorded') AS cashier_name
                        FROM assignments a JOIN sales s ON s.sale_id=a.sale_id
                        JOIN employees e ON e.employee_id=a.employee_id
                        LEFT JOIN cashiers c ON c.cashier_id=s.cashier_id''', 's.sale_date', 's.cashier_id'),
        }
        query, date_column, cashier_column = queries[report]
        query += f' WHERE {date_column} BETWEEN ? AND ?'
        params = [start.isoformat(), end.isoformat()]
        if cashier_id is not None:
            query += f' AND {cashier_column}=?'
            params.append(cashier_id)
        if sale_kind:
            query += ' AND s.kind=?'
            params.append(sale_kind)
        if payment_method:
            query += ' AND p.method=?'
            params.append(payment_method)
        with self.connect() as db:
            return [dict(row) for row in db.execute(query + f' ORDER BY {date_column}', params)]

    def cashier_activity(self):
        self.require_manager()
        with self.connect() as db:
            totals = {}
            for row in db.execute('SELECT cashier_id,name FROM cashiers ORDER BY name'):
                totals[row['cashier_id']] = {'cashier_id': row['cashier_id'], 'name': row['name'],
                    'sales_count': 0, 'payment_count': 0, 'charges': Decimal(0),
                    'receipts': Decimal(0), 'expenses': Decimal(0)}
            for table, amount_field, count_field in (
                ('sales', 'charges', 'sales_count'),
                ('payments', 'receipts', 'payment_count'),
                ('expenses', 'expenses', None),
            ):
                for row in db.execute(f'SELECT cashier_id,amount FROM {table}'):
                    if row['cashier_id'] in totals:
                        cashier = totals[row['cashier_id']]
                        cashier[amount_field] += money(row['amount'])
                        if count_field:
                            cashier[count_field] += 1
        return list(totals.values())
