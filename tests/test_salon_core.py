from datetime import date
from decimal import Decimal
import pytest
from auth_helpers import SalonDatabase
from salon_core import (ServiceTransaction, ProductTransaction, Transaction, Payment,
                        ExpenseAllowance, MovingAverageForecaster, Reconciliation)


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


def test_forecast_history_ends_yesterday_and_excludes_future(tmp_path):
    from datetime import timedelta

    db = SalonDatabase(tmp_path / 'forecast.sqlite3')
    yesterday = date.today() - timedelta(days=1)
    db.record_sale('Y', yesterday, 'Product', 'Oil', ProductTransaction(1, '100'))
    db.record_sale('T', date.today(), 'Product', 'Oil', ProductTransaction(1, '200'))
    db.record_sale('F', date.today() + timedelta(days=1), 'Product', 'Oil', ProductTransaction(1, '300'))
    history = db.daily_revenue(7)
    assert history[-1] == (yesterday, Decimal('100'))
    assert sum(amount for _, amount in history) == 100
    with pytest.raises(ValueError):
        db.daily_revenue(0)


def test_sale_type_matches_transaction(tmp_path):
    db = SalonDatabase(tmp_path / 'types.sqlite3')
    with pytest.raises(ValueError, match='match the sale type'):
        db.record_sale('P', date.today(), 'Product', 'Oil', ServiceTransaction(100))
    assert db.sales() == []


def test_reports_keep_decimal_precision(tmp_path):
    db = SalonDatabase(tmp_path / 'precision.sqlite3')
    db.add_cashier('C', 'Cashier')
    db.add_employee('E', 'Employee', 'Hair', 30)
    for sale_id, amount in [('S1', '0.1'), ('S2', '0.2')]:
        db.record_sale(sale_id, date.today(), 'Service', 'Hair', ServiceTransaction(amount), [('E', 100)], cashier_id='C')
    employee = db.productivity()[0]
    assert employee['revenue'] == Decimal('0.3')
    assert employee['expected_wages'] == Decimal('0.09')
    assert db.cashier_activity()[0]['charges'] == Decimal('0.3')
