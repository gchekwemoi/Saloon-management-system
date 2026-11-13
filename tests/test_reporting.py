import csv
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest

from auth_helpers import SalonDatabase
from reporting import report_csv, summarize_records
from salon_core import Payment, ProductTransaction, ServiceTransaction


@pytest.fixture
def db(tmp_path):
    db = SalonDatabase(tmp_path / 'reports.sqlite3')
    db.add_cashier('C1', 'Alice')
    db.add_cashier('C2', 'Betty')
    db.add_employee('E1', 'Stylist', 'Hair', 30)
    db.record_paid_sale('S1', date(2026, 11, 1), 'Service', 'Hair', ServiceTransaction(100000), [('E1', 100)], cashier_id='C1', payment=Payment(100000, 'Cash'))
    db.record_paid_sale('P1', date(2026, 11, 2), 'Product', 'Oil', ProductTransaction(1, 20000), cashier_id='C2', payment=Payment(20000, 'Mobile Money', 'REF1'))
    db.record_paid_sale('P2', date(2026, 10, 31), 'Product', 'Oil', ProductTransaction(1, 7000), cashier_id='C1', payment=Payment(7000, 'Cash'))
    db.approve_allowance(10000)
    db.add_expense(1, 'Supplies', 2000, cashier_id='C1')
    return db


def test_date_cashier_and_type_filters(db):
    rows = db.report_records('Sales', date(2026, 11, 1), date(2026, 11, 2))
    assert {row['sale_id'] for row in rows} == {'S1', 'P1'}
    assert len(db.report_records('Sales', date(2026, 11, 1), date(2026, 11, 2), 'C1', 'Service')) == 1
    assert db.report_records('Sales', date(2026, 11, 1), date(2026, 11, 2), 'C1', 'Product') == []


def test_payment_and_employee_reports(db):
    rows = db.report_records('Payments', date(2026, 11, 1), date(2026, 11, 2), payment_method='Mobile Money')
    assert [row['sale_id'] for row in rows] == ['P1']
    rows = db.report_records('Employee allocations', date(2026, 11, 1), date(2026, 11, 2))
    assert rows[0]['employee_name'] == 'Stylist'
    assert rows[0]['amount'] == '100000'
    assert rows[0]['expected_wages'] == '30000'
    assert db.report_records('Expenses', date(2026, 1, 1), date(2026, 12, 31), 'C2') == []


@pytest.mark.parametrize('frequency,expected', [('Daily', 2), ('Weekly', 2), ('Monthly', 1)])
def test_summary_totals(db, frequency, expected):
    rows = db.report_records('Sales', date(2026, 11, 1), date(2026, 11, 2))
    grouped = summarize_records(rows, frequency)
    assert len(grouped) == expected
    assert sum(row['amount'] for row in grouped) == Decimal('120000')
    assert sum(row['expected_wages'] for row in grouped) == Decimal('30000')


def test_csv_escapes_formula_and_keeps_decimal():
    data = report_csv([{'description': '=HYPERLINK("bad")', 'amount': Decimal('0.30')}])
    rows = list(csv.DictReader(StringIO(data.decode('utf-8-sig'))))
    assert rows[0]['description'].startswith("'=")
    assert rows[0]['amount'] == '0.30'
    assert report_csv([]) == b''


def test_invalid_filters_and_cashier_blocked(db):
    with pytest.raises(ValueError):
        db.report_records('Sales', date(2026, 11, 2), date(2026, 11, 1))
    with pytest.raises(ValueError):
        db.report_records('Expenses', date(2026, 11, 1), date(2026, 11, 2), sale_kind='Service')
    db.create_account('alice', 'cashier-password-123', 'Cashier', 'C1')
    db.login('alice', 'cashier-password-123')
    with pytest.raises(PermissionError):
        db.report_records('Sales', date(2026, 1, 1), date(2026, 12, 31))
