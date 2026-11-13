"""Tests for new salon name and multi-cashier tracking."""
from datetime import date
from decimal import Decimal
import sqlite3
import pytest
from auth_helpers import SalonDatabase
from salon_core import  ServiceTransaction, Payment


def test_identity_and_cashier_attribution(tmp_path):
    path = tmp_path / 'salon.sqlite3'
    db = SalonDatabase(path)
    assert db.salon_name() == 'Saloon Management System'
    db.set_salon_name('Purple Rose Studio')
    assert db.salon_name() == 'Purple Rose Studio'
    db.add_cashier('C01','Alice')
    db.add_cashier('C02','Betty')
    assert len(db.cashiers()) == 2
    db.add_employee('E01','Worker','Braiding',30)
    db.record_sale('S01', date.today(), 'Service','Knotless',ServiceTransaction(Decimal('100000')), [('E01',100)], cashier_id='C01')
    db.add_payment('S01',Payment(Decimal('80000'),'Cash'),cashier_id='C02')
    assert db.sales()[0]['cashier_name'] == 'Alice'
    results = {r['cashier_id']:r for r in db.cashier_activity()}
    assert results['C01']['sales_count'] == 1
    assert results['C02']['payment_count'] == 1
    assert results['C02']['receipts'] == 80000
    assert db.summary().unpaid_balance() == 20000
    assert db.payments()[0]['cashier_name'] == 'Betty'
    db.approve_allowance(10000)
    db.add_expense(db.allowances()[0]['allowance_id'], 'Supplies', 2000, cashier_id='C01')
    assert db.expenses()[0]['cashier_name'] == 'Alice'
    reopened = SalonDatabase(path)
    assert reopened.salon_name() == 'Purple Rose Studio'
    assert reopened.summary().expenses == 2000


def test_invalid_cashier_and_duplicate_id(tmp_path):
    db=SalonDatabase(tmp_path/'db.sqlite3')
    with pytest.raises(ValueError):
        db.set_salon_name('  ')
    with pytest.raises(ValueError):
        db.record_sale('P01',date.today(),'Product','Oil',ServiceTransaction(500),cashier_id='BAD')
    db.add_cashier('C1','Alice')
    with pytest.raises(sqlite3.IntegrityError):
        db.add_cashier('C1','Another')


def test_database_migration_preserves_records(tmp_path):
    path=tmp_path/'legacy.sqlite3'
    db=SalonDatabase(path)
    with db.connect() as con:
        con.execute('INSERT INTO sales (sale_id,sale_date,kind,description,amount,expected_wages) VALUES (?,?,?,?,?,?)',
                    ('OLD','2026-01-01','Product','Oil','7000','0'))
        for table in ('sales','payments','expenses'):
            con.execute(f'ALTER TABLE {table} DROP COLUMN cashier_id')
    upgraded=SalonDatabase(path)
    assert upgraded.sales()[0]['sale_id']=='OLD'
    assert upgraded.sales()[0]['cashier_name']=='Not recorded'
