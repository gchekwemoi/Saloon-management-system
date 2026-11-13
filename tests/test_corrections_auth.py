from datetime import date
import json
import pytest
from auth_helpers import SalonDatabase
from salon_core import SalonDatabase as RawDatabase, ServiceTransaction, ProductTransaction, Payment


@pytest.fixture
def db(tmp_path):
    db = SalonDatabase(tmp_path / 'salon.db')
    db.add_cashier('C1', 'Alice')
    db.add_cashier('C2', 'Betty')
    db.add_employee('E1', 'Stylist', 'Hair', 30)
    db.record_sale('S1', date.today(), 'Service', 'Hair', ServiceTransaction(100000), [('E1', 100)], cashier_id='C1')
    db.record_sale('P1', date.today(), 'Product', 'Oil', ProductTransaction(2, 10000), cashier_id='C1')
    db.add_payment('S1', Payment(50000, 'Cash'), cashier_id='C2')
    db.approve_allowance(10000)
    db.add_expense(1, 'Supplies', 3000, cashier_id='C1')
    return db


def test_reconciliation_and_audit(db):
    db.correct_transaction('sales', 'S1', {'amount': '80000'}, 'Price entered incorrectly')
    db.correct_transaction('sales', 'P1', {'amount': '15000'}, 'Retail discount')
    db.correct_transaction('payments', 1, {'amount': '40000', 'method': 'Mobile Money', 'reference': 'REF'}, 'Receipt correction')
    db.correct_transaction('expenses', 1, {'amount': '2000'}, 'Receipt confirmed')
    summary = db.summary()
    assert (summary.charges, summary.receipts, summary.expenses, summary.expected_wages) == (95000, 40000, 2000, 24000)
    assert summary.unpaid_balance() == 55000
    assert summary.net_cash_after_expenses() == 38000
    assert db.remaining_allowance(1) == 8000
    assert db.productivity()[0]['revenue'] == 80000
    audit = db.audit_log()
    assert len(audit) == 4
    assert json.loads(audit[-1]['previous_values'])['amount'] == '100000'
    assert audit[-1]['username'] == 'manager'
    assert audit[-1]['corrected_at'] and audit[-1]['reason']
    reopened = SalonDatabase(db.path)
    assert reopened.summary() == summary
    assert len(reopened.audit_log()) == 4


@pytest.mark.parametrize('entity,key,changes', [
    ('sales', 'S1', {'amount': '49999'}),
    ('sales', 'S1', {'assignments': [('E1', 80)]}),
    ('sales', 'S1', {'assignments': [('E1', 50), ('E1', 50)]}),
    ('sales', 'S1', {'assignments': [('unknown', 100)]}),
    ('sales', 'P1', {'assignments': [('E1', 100)]}),
    ('payments', 1, {'amount': '100001'}),
    ('payments', 1, {'sale_id': 'P1'}),
    ('payments', 1, {'method': 'Mobile Money', 'reference': ''}),
    ('expenses', 1, {'amount': '10001'}),
    ('expenses', 1, {'allowance_id': 999}),
])
def test_invalid_corrections_roll_back(db, entity, key, changes):
    before = db.summary()
    with pytest.raises(ValueError):
        db.correct_transaction(entity, key, changes, 'Invalid correction')
    assert db.summary() == before
    assert db.audit_log() == []
    assert db.assignments_for_sale('S1')[0]['attributed_revenue'] == '100000'


def test_cashier_permissions_and_attribution(db):
    db.create_account('alice', 'cashier-password-123', 'Cashier', 'C1')
    cashier = RawDatabase(db.path)
    cashier.login('alice', 'cashier-password-123')
    for action in (lambda: cashier.set_salon_name('Forbidden'), lambda: cashier.add_cashier('C3', 'X'),
                   lambda: cashier.approve_allowance(10), lambda: cashier.summary(),
                   lambda: cashier.audit_log(), lambda: cashier.create_account('x', 'password-long-enough', 'Owner/Manager'),
                   lambda: cashier.correct_transaction('sales', 'P1', {'cashier_id': 'C2'}, 'No')):
        with pytest.raises(PermissionError):
            action()
    assert 'expected_wages' not in cashier.sales()[0]
    service = next(row for row in cashier.sales() if row['sale_id'] == 'S1')
    assert service['service_employees'] == 'Stylist (E1)'
    product = next(row for row in cashier.sales() if row['sale_id'] == 'P1')
    assert product['service_employees'] == 'Not applicable'
    assert 'wage_rate' not in cashier.employees()[0]
    cashier.record_sale('P2', date.today(), 'Product', 'Oil', ProductTransaction(1, 100))
    cashier.record_sale('S2', date.today(), 'Service', 'Hair', ServiceTransaction(1000), [('E1', 100)])
    assert next(x for x in db.sales() if x['sale_id'] == 'P2')['cashier_id'] == 'C1'
    with pytest.raises(PermissionError):
        cashier.add_payment('P2', Payment(10, 'Cash'), cashier_id='C2')
    cashier.logout()
    with pytest.raises(PermissionError):
        cashier.add_payment('P2', Payment(10, 'Cash'))


def test_setup_and_sessions(tmp_path, monkeypatch):
    db = RawDatabase(tmp_path / 'new.db')
    with pytest.raises(PermissionError):
        db.add_cashier('C1', 'No login')
    db.setup_manager('manager', 'long-password-value')
    with pytest.raises(PermissionError):
        db.setup_manager('other', 'long-password-value')
    with pytest.raises(PermissionError):
        db.login('manager', 'wrong-password-value')
    token = db.login('manager', 'long-password-value')
    with db.connect() as con:
        assert 'long-password-value' not in con.execute('SELECT password_hash FROM accounts').fetchone()[0]
        assert token != con.execute('SELECT token_hash FROM sessions').fetchone()[0]
        con.execute('UPDATE sessions SET expires_at=0')
    with pytest.raises(PermissionError):
        db.set_salon_name('Expired')


def test_migration_preserves_existing_records(db):
    before = db.summary()
    with db.connect() as con:
        con.execute('DROP TABLE correction_audit')
    reopened = SalonDatabase(db.path)
    assert reopened.summary() == before
    assert reopened.audit_log() == []
    assert len(reopened.sales()) == 2


def test_blank_reason_and_allowance_transfer(db):
    with pytest.raises(ValueError):
        db.correct_transaction('expenses', 1, {'amount': '1000'}, ' ')
    db.approve_allowance(5000)
    db.correct_transaction('expenses', 1, {'allowance_id': 2, 'amount': '4000'}, 'Use correct allowance')
    assert db.remaining_allowance(1) == 10000
    assert db.remaining_allowance(2) == 1000


def test_operating_activity_totals_and_cashier_scope(db):
    db.record_sale('P2', date.today(), 'Product', 'Shampoo', ProductTransaction(1, 7000), cashier_id='C2')
    db.add_expense(1, 'Transport', 1000, cashier_id='C2')
    totals = db.operating_activity()
    assert totals['product_total'] == 27000
    assert totals['expense_total'] == 4000
    assert len(totals['products']) == 2
    db.create_account('alice', 'cashier-password-123', 'Cashier', 'C1')
    db.login('alice', 'cashier-password-123')
    totals = db.operating_activity()
    assert totals['product_total'] == 20000
    assert totals['expense_total'] == 3000
    assert all(row['cashier_id'] == 'C1' for row in totals['products'] + totals['expenses'])
    assert all('expected_wages' not in row for row in totals['products'])


@pytest.mark.parametrize('entity,key,new_amount', [('sales', 'S1', '80000'), ('sales', 'P1', '15000'), ('payments', 1, '40000'), ('expenses', 1, '2000')])
def test_cashier_same_day_correction_and_expiry(db, entity, key, new_amount):
    from datetime import datetime, timezone, timedelta
    today = datetime.now(timezone(timedelta(hours=3))).date()
    date_field = {'sales': 'sale_date', 'payments': 'paid_on', 'expenses': 'expense_date'}[entity]
    key_field = {'sales': 'sale_id', 'payments': 'payment_id', 'expenses': 'expense_id'}[entity]
    cid = 'C2' if entity == 'payments' else 'C1'
    with db.connect() as con:
        con.execute(f'UPDATE {entity} SET {date_field}=? WHERE {key_field}=?', (today.isoformat(), key))
    db.create_account('operator', 'operator-password-123', 'Cashier', cid)
    manager_token = db.session_token
    db.login('operator', 'operator-password-123')
    assert db.cashier_editable_records(entity)
    db.correct_transaction(entity, key, {'amount': new_amount}, 'Same-day entry correction')
    with pytest.raises(PermissionError):
        db.correct_transaction(entity, key, {date_field: today.isoformat()}, 'Change date')
    with db.connect() as con:
        con.execute(f'UPDATE {entity} SET {date_field}=? WHERE {key_field}=?', ((today-timedelta(days=1)).isoformat(), key))
    with pytest.raises(PermissionError):
        db.correct_transaction(entity, key, {'amount': new_amount}, 'Too late')
    db.session_token = manager_token
    assert db.audit_log()[0]['username'] == 'operator'
    db.correct_transaction(entity, key, {'amount': new_amount}, 'Manager can correct old records')


@pytest.mark.parametrize('method,reference', [('Cash', ''), ('Mobile Money', 'MM-123')])
def test_sale_and_payment_saved_together(db, method, reference):
    db.record_sale('PAID', date.today(), 'Product', 'Oil', ProductTransaction(2, 10000), cashier_id='C1', payment=Payment(20000, method, reference))
    payment = next(row for row in db.payments() if row['sale_id'] == 'PAID')
    assert (payment['amount'], payment['method'], payment['cashier_id']) == ('20000', method, 'C1')
    with pytest.raises(ValueError):
        db.record_sale('INVALID', date.today(), 'Product', 'Oil', ProductTransaction(2, 10000), cashier_id='C1', payment=Payment(10000, 'Cash'))
    assert not any(row['sale_id'] == 'INVALID' for row in db.sales())
    with pytest.raises(Exception):
        db.record_sale('PAID', date.today(), 'Product', 'Oil', ProductTransaction(2, 10000), cashier_id='C1', payment=Payment(20000, method, reference))
    assert len([row for row in db.payments() if row['sale_id'] == 'PAID']) == 1


def test_dashboard_counts_cashier_receipts_for_other_cashiers_sales(db):
    db.create_account('betty', 'cashier-password-123', 'Cashier', 'C2')
    db.login('betty', 'cashier-password-123')
    totals = db.cashier_dashboard()
    assert totals['receipts'] == 50000
    assert totals['charges'] == 0
    assert totals['outstanding'] == 0


def test_legacy_cash_migration_settles_only_remainder_once(db):
    with db.connect() as con:
        original_payments = [dict(row) for row in con.execute('SELECT * FROM payments')]
        con.execute("DELETE FROM schema_migrations WHERE name='legacy_outstanding_as_cash_v1'")
    upgraded = SalonDatabase(db.path)
    assert upgraded.summary().unpaid_balance() == 0
    assert upgraded.summary().receipts == 120000
    assert upgraded.summary().expected_wages == 30000
    payments = upgraded.payments()
    assert len(payments) == 3
    for original in original_payments:
        assert all(next(row for row in payments if row['payment_id'] == original['payment_id'])[key] == value for key, value in original.items())
    added = [row for row in payments if row['reference'] == 'Legacy balance settled as Cash']
    assert {row['sale_id']: row['amount'] for row in added} == {'S1': '50000', 'P1': '20000'}
    assert all(row['method'] == 'Cash' and row['cashier_id'] == 'C1' for row in added)
    assert len(upgraded.audit_log()) == 2
    reopened = SalonDatabase(db.path)
    assert len(reopened.payments()) == 3
    assert len(reopened.audit_log()) == 2


def test_cashier_collection_dashboard_reconciles_methods(db):
    db.record_paid_sale('MM', date.today(), 'Product', 'Oil', ProductTransaction(1, 20000), cashier_id='C1', payment=Payment(20000, 'Mobile Money', 'MM123'))
    db.record_paid_sale('OTHER', date.today(), 'Product', 'Oil', ProductTransaction(1, 9000), cashier_id='C2', payment=Payment(9000, 'Cash'))
    db.create_account('alice', 'cashier-password-123', 'Cashier', 'C1')
    db.login('alice', 'cashier-password-123')
    totals = db.cashier_collection_dashboard()
    assert totals == {'collected': 70000, 'cash': 50000, 'mobile_money': 20000}
    assert 'outstanding' not in totals
