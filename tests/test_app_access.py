from pathlib import Path
from streamlit.testing.v1 import AppTest
from auth_helpers import SalonDatabase


APP = Path(__file__).resolve().parents[1] / 'app.py'


def test_first_manager_setup_without_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('SALON_SETUP_TOKEN', raising=False)
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert len(app.text_input) == 3
    app.text_input[0].set_value('Gloria')
    app.text_input[1].set_value('manager-password-123')
    app.text_input[2].set_value('manager-password-123')
    app.button[0].click().run()
    assert not app.exception
    assert any(heading.value == 'Sign in' for heading in app.subheader)


def test_startup_refreshes_pre_authentication_module(tmp_path, monkeypatch):
    import salon_core

    monkeypatch.chdir(tmp_path)
    # Model an existing Streamlit server holding the old imported class.
    class LegacyDatabase:
        pass

    original_module = dict(vars(salon_core))
    try:
        salon_core.SalonDatabase = LegacyDatabase
        app = AppTest.from_file(str(APP)).run()
        assert not app.exception
        assert hasattr(salon_core.SalonDatabase, 'has_accounts')
        assert any('Set up the first' in heading.value for heading in app.subheader)
    finally:
        # Reload creates new class identities; preserve those imported by other
        # regression tests in this process.
        vars(salon_core).update(original_module)


def test_startup_refreshes_module_missing_activity(tmp_path, monkeypatch):
    import salon_core

    monkeypatch.chdir(tmp_path)
    original_module = dict(vars(salon_core))
    class OlderDatabase:
        def has_accounts(self):
            return False

    try:
        salon_core.SalonDatabase = OlderDatabase
        app = AppTest.from_file(str(APP)).run()
        assert not app.exception
        assert hasattr(salon_core.SalonDatabase, 'operating_activity')
    finally:
        vars(salon_core).update(original_module)


def test_login_and_cashier_navigation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = SalonDatabase(tmp_path / 'salon.sqlite3')
    db.add_cashier('C1', 'Alice')
    db.create_account('alice', 'cashier-password-123', 'Cashier', 'C1')
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert not app.sidebar.radio
    assert any('Cashier and Owner/Manager login' in caption.value for caption in app.caption)
    assert all('\u00e2' not in block.value and '\u00c3' not in block.value for block in app.markdown)
    app.text_input[0].set_value('alice')
    app.text_input[1].set_value('cashier-password-123')
    app.button[0].click().run()
    assert not app.exception
    options = app.sidebar.radio[0].options
    assert 'Reports' not in options
    assert 'Settings & Cashiers' not in options
    assert 'Corrections' not in options
    assert options == ['Dashboard', 'Record Service', 'Sell Product', 'Record Expense', 'Sales Register']
    assert len(app.metric) == 5
    assert all('wage' not in metric.label.lower() for metric in app.metric)
    app.sidebar.radio[0].set_value('Sales Register').run()
    assert not app.exception


def test_manager_dashboard_and_corrections(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = SalonDatabase(tmp_path / 'salon.sqlite3')
    token = db.session_token
    app = AppTest.from_file(str(APP))
    app.session_state['auth_token'] = token
    app.run()
    assert not app.exception

    assert len(app.metric) == 6
    app.sidebar.radio[0].set_value('Corrections').run()
    assert not app.exception


def test_manager_creates_linked_cashier_login(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = SalonDatabase(tmp_path / 'salon.sqlite3')
    db.add_cashier('C1', 'Alice')
    db.add_cashier('C2', 'Betty')
    app = AppTest.from_file(str(APP))
    app.session_state['auth_token'] = db.session_token
    app.run()
    app.sidebar.radio[0].set_value('Settings & Cashiers').run()
    next(w for w in app.text_input if w.label == 'New username').set_value('betty')
    next(w for w in app.text_input if w.label.startswith('New password')).set_value('betty-password-123')
    next(w for w in app.selectbox if w.label.startswith('Linked cashier')).set_value('C2')
    next(w for w in app.button if w.label == 'Create account').click().run()
    assert not app.exception
    assert app.success
    db.login('betty', 'betty-password-123')
    assert db.current_user()['cashier_id'] == 'C2'
    assert db.current_user()['role'] == 'Cashier'


def test_manager_signs_out_for_cashier_login(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = SalonDatabase(tmp_path / 'salon.sqlite3')
    app = AppTest.from_file(str(APP))
    app.session_state['auth_token'] = db.session_token
    app.run()
    next(button for button in app.sidebar.button if button.label == 'Sign out').click().run()
    assert not app.exception
    assert not app.sidebar.radio
    assert any('Cashier and Owner/Manager login' in caption.value for caption in app.caption)


def test_product_sale_records_full_payment_on_dashboard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = SalonDatabase(tmp_path / 'salon.sqlite3')
    db.add_cashier('C1', 'Alice')
    db.create_account('alice', 'cashier-password-123', 'Cashier', 'C1')
    db.login('alice', 'cashier-password-123')
    app = AppTest.from_file(str(APP))
    app.session_state['auth_token'] = db.session_token
    app.run()
    app.sidebar.radio[0].set_value('Sell Product').run()
    next(w for w in app.text_input if w.label == 'Product description').set_value('Oil')
    next(w for w in app.number_input if w.label == 'Agreed unit price (UGX)').set_value(20000)
    next(w for w in app.selectbox if w.label == 'Payment method').set_value('Mobile Money')
    next(w for w in app.text_input if w.label == 'Mobile Money reference').set_value('MM123')
    next(w for w in app.button if w.label == 'Record product sale').click().run()
    assert not app.exception
    assert app.success
    app.sidebar.radio[0].set_value('Dashboard').run()
    assert app.metric[0].value == 'UGX 20,000'
    assert app.metric[1].value == 'UGX 0'
    assert app.metric[2].value == 'UGX 20,000'
    assert [m.label for m in app.metric[:3]] == ['Total collected', 'Cash', 'Mobile Money']


def test_manager_filtered_report_download(tmp_path, monkeypatch):
    from datetime import date
    from salon_core import Payment, ProductTransaction

    monkeypatch.chdir(tmp_path)
    db = SalonDatabase(tmp_path / 'salon.sqlite3')
    db.add_cashier('C1', 'Alice')
    db.record_paid_sale('P1', date.today(), 'Product', 'Oil', ProductTransaction(1, 20000), cashier_id='C1', payment=Payment(20000, 'Cash'))
    app = AppTest.from_file(str(APP))
    app.session_state['auth_token'] = db.session_token
    app.run()
    app.sidebar.radio[0].set_value('Reports').run()
    assert not app.exception
    assert len(app.get('download_button')) == 1
    next(w for w in app.selectbox if w.label == 'Summary frequency').set_value('Monthly').run()
    assert not app.exception
    assert len(app.get('download_button')) == 1
