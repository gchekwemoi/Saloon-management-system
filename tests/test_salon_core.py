from datetime import date
from decimal import Decimal
import pytest
from salon_core import (ServiceTransaction, ProductTransaction, Transaction, Payment,
                        ExpenseAllowance, SalonDatabase, MovingAverageForecaster, Reconciliation)


def test_polymorphism():
    items: list[Transaction] = [ServiceTransaction('150000'), ProductTransaction(3, '8000')]
    assert sum((i.calculate_total() for i in items), Decimal('0')) == Decimal('174000')


def test_invalid_product_quantity():
    with pytest.raises(ValueError): ProductTransaction(True, '1000')


def test_mobile_money_reference():
    with pytest.raises(ValueError): Payment('1000', 'Mobile Money', '')


def test_allowance():
    assert ExpenseAllowance('50000', '20000').remaining_balance() == Decimal('30000')


def test_db_workflow(tmp_path):
    db = SalonDatabase(tmp_path / 'test.sqlite3')
    db.add_employee('E01', 'A', 'Braiding', '30')
    db.add_employee('E02', 'B', 'Braiding', '35')
    db.record_sale('S01', date.today(), 'Service', 'Braids', ServiceTransaction('150000'),
                   [('E01', 60), ('E02', 40)])
    db.record_sale('P01', date.today(), 'Product', 'Oil', ProductTransaction(2, '10000'))
    db.add_payment('S01', Payment('120000', 'Cash'))
    db.approve_allowance('10000', 'Supplies')
    aid = db.allowances()[0]['allowance_id']
    db.add_expense(aid, 'Supplies', '4000')
    totals = db.summary()
    assert totals.charges == Decimal('170000')
    assert totals.receipts == Decimal('120000')
    assert totals.unpaid_balance() == Decimal('50000')
    assert totals.expected_wages == Decimal('48000')
    assert totals.expenses == Decimal('4000')
    assert db.remaining_allowance(aid) == Decimal('6000')
    assert len(db.productivity()) == 2


def test_shares_must_total_100(tmp_path):
    db = SalonDatabase(tmp_path / 'test.sqlite3')
    db.add_employee('E01', 'A', 'Braiding', 30)
    with pytest.raises(ValueError):
        db.record_sale('S01', date.today(), 'Service', 'Braiding', ServiceTransaction('10000'), [('E01', 90)])


def test_payment_cannot_exceed_sale(tmp_path):
    db = SalonDatabase(tmp_path / 'test.sqlite3')
    db.record_sale('P01', date.today(), 'Product', 'Beads', ProductTransaction(1, 5000))
    with pytest.raises(ValueError): db.add_payment('P01', Payment(6000, 'Cash'))


def test_moving_average():
    assert MovingAverageForecaster().forecast([Decimal('10'), Decimal('20')], 2) == [Decimal('15')] * 2
