"""Saloon Management System: customizable coursework demonstration.

Run: python -m streamlit run app.py
Authenticated manager and cashier workspace.
"""
from datetime import date, timedelta
import sqlite3
from html import escape

import pandas as pd
import streamlit as st

# Streamlit can retain imported modules while rerunning an updated app.py.
# Refresh the complete business module before importing its classes when an
# already-running server still holds the pre-authentication implementation.
import importlib
import salon_core

if any(not hasattr(salon_core.SalonDatabase, method) for method in
       ('has_accounts', 'operating_activity', 'cashier_collection_dashboard', 'cashier_editable_records', 'record_paid_sale', 'settle_legacy_cash_balances', 'report_records')):
    importlib.invalidate_caches()
    salon_core = importlib.reload(salon_core)

from salon_core import (
    SalonDatabase, Payment, ProductTransaction, ServiceTransaction,
    MovingAverageForecaster, WeekdayForecaster, money,
)

from reporting import report_csv, summarize_records

st.set_page_config(page_title="Salon Studio | Management", page_icon=":scissors:", layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');
:root { --violet:#5c287d; --pink:#e35f9b; --gold:#d5a849; --ink:#17121d; }
html, body, [class*="css"], [data-testid="stAppViewContainer"] { font-family:'DM Sans',sans-serif; }
[data-testid="stAppViewContainer"] { background:radial-gradient(circle at 94% 0%,#fce8f2 0%,#faf8fd 32%,#faf8fd 100%); color:#24182b; }
[data-testid="stSidebar"] { background:linear-gradient(160deg,#201126,#452056 62%,#341944); }
[data-testid="stSidebar"] * { color:#fff2fb !important; }
[data-testid="stSidebar"] [data-baseweb="radio"] {background:transparent}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { font-weight:500; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] * { color:#f0d3ec !important; }
[data-testid="stSidebar"] [data-baseweb="select"] * { color:#2c1833 !important; }
h1,h2,h3 { font-family:'Playfair Display',Georgia,serif !important; letter-spacing:-.025em; color:#30143f !important; }
h1 {font-size:2.25rem !important} h2 {font-size:1.5rem !important}
.stButton>button[kind="primary"], [data-testid="stFormSubmitButton"] button {background:linear-gradient(100deg,#642e85,#a43c84) !important;color:white !important;border:0 !important;border-radius:12px !important;font-weight:700;padding:.55rem 1.25rem;box-shadow:0 5px 15px #59287624;}
.stButton>button:not([kind="primary"]) {border:1px solid #d7b2ce;border-radius:12px;}
[data-testid="stMetric"] {border:1px solid #eadbe9;background:white;border-radius:17px;padding:17px 20px;box-shadow:0 6px 22px #39184c0a;}
[data-testid="stMetricLabel"] {color:#715e75} [data-testid="stMetricValue"] {color:#54246d;font-weight:700;}
[data-testid="stForm"] {background:#ffffff;border:1px solid #eadce9;border-radius:20px;padding:22px;box-shadow:0 7px 28px #37134208;}
[data-testid="stDataFrame"] {border:1px solid #eadce9;border-radius:14px;overflow:hidden;}
[data-testid="stAlert"] {border-radius:12px;}
.hero {background:linear-gradient(112deg,#211127 0%,#56296a 56%,#9d3f7c 100%);border-radius:22px;padding:29px 32px;color:#fff;margin:8px 0 24px;position:relative;overflow:hidden;box-shadow:0 12px 32px #3a1b4d22;}
.hero:before {content:'*';font-size:150px;position:absolute;right:32px;top:-65px;color:#d5a84930;}
.hero .eyebrow {letter-spacing:.2em;text-transform:uppercase;font-size:11px;color:#f6c87e;font-weight:700;}
.hero h1 {color:white !important;font-size:2.15rem !important;margin:.25rem 0;}
.hero p {color:#f5dfea;margin:0;font-size:14px;}
.section-note {color:#836c86;font-size:13px;margin-top:-5px;margin-bottom:18px;}
.goldline {width:46px;height:3px;background:#d5a849;border-radius:10px;margin:8px 0 18px;}
.brand {font-family:Georgia,serif;font-size:26px;font-weight:bold;color:#ffe9f5;text-align:center;line-height:1.2;margin:18px 0 2px;}
.brand-sub {font-size:11px;letter-spacing:.2em;text-align:center;color:#f2bb72;margin-bottom:25px;}
[data-testid="stSidebar"] hr {border-color:#ffffff26;}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] > div {font-size:clamp(1rem,2.2vw,2rem) !important;white-space:normal !important;overflow:visible !important;text-overflow:clip !important;overflow-wrap:anywhere;}
[data-testid="stMetric"] {min-width:0;border-top:3px solid #d5a849;}
/* Explicit colors avoid inherited dark-theme text on light controls. */
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] *,
[data-testid="stSidebar"] [data-testid="stRadio"] label * {color:#fff2fb !important;opacity:1 !important;}
[data-testid="stSidebar"] button {background:#642e85 !important;border:1px solid #e8bf62 !important;}
[data-testid="stSidebar"] button * {color:#ffffff !important;}
[data-testid="stAlert"] {background:#f6eaf6 !important;border:1px solid #b87aa5 !important;}
[data-testid="stAlert"] * {color:#30143f !important;}
[data-testid="InputInstructions"] {display:none !important;}
[data-testid="stTextInput"] input {color:#24182b !important;background:#f5e8f2 !important;}
[data-testid="stTextInput"] [data-baseweb="input"] {background:#f5e8f2 !important;border-color:#a43c84 !important;}
[data-testid="stTextInput"] button {color:#30143f !important;background:#f5e8f2 !important;}
[data-testid="stTextInput"] button svg {fill:currentColor !important;}
</style>""", unsafe_allow_html=True)


def fmt(value):
    return f"UGX {money(value):,.0f}"


def save(action, message="Saved successfully"):
    try:
        result = action()
        st.success(message)
        return result
    except (ValueError, TypeError, PermissionError, sqlite3.Error) as exc:
        st.error(str(exc))
        return None


def show_table(rows, empty="No records yet"):
    if rows:
        frame = pd.DataFrame(rows)
        amounts = {'amount', 'expected_wages', 'revenue', 'charges', 'receipts', 'expenses', 'attributed_revenue', 'expected_wage'}
        for column in amounts.intersection(frame.columns):
            frame[column] = frame[column].map(lambda v: fmt(v) if v is not None else '')
        frame = frame.rename(columns=lambda c: c.replace('_', ' ').title())
        st.dataframe(frame, use_container_width=True, hide_index=True)
    else:
        st.info(empty)


db = SalonDatabase()
salon_name = db.salon_name()
st.sidebar.markdown(f'<div class="brand">&#10022;  {escape(salon_name)}</div><div class="brand-sub">BEAUTY  |  BUSINESS  |  INSIGHTS</div>', unsafe_allow_html=True)
if not db.has_accounts():
    st.subheader('Set up the first Owner/Manager')
    st.info('Choose your manager username and password. Initial setup closes once the first account is created.')
    with st.form('setup'):
        username = st.text_input('Manager username')
        password = st.text_input('Manager password (at least 12 characters)', type='password')
        confirm = st.text_input('Confirm password', type='password')
        if st.form_submit_button('Create initial manager'):
            if password != confirm:
                st.error('Passwords do not match')
            else:
                try:
                    db.setup_manager(username, password)
                    st.rerun()
                except (ValueError, PermissionError, sqlite3.Error) as exc:
                    st.error(str(exc))
    st.stop()
db.session_token = st.session_state.get('auth_token')
try:
    user = db.current_user()
except PermissionError:
    with st.form('login'):
        st.subheader('Sign in')
        st.caption('Cashier and Owner/Manager login: use your individual username and password. Your account determines your access.')
        username = st.text_input('Username')
        password = st.text_input('Password', type='password')
        if st.form_submit_button('Sign in'):
            try:
                st.session_state.auth_token = db.login(username, password)
                st.rerun()
            except (PermissionError, ValueError) as exc:
                st.error(str(exc))
    st.stop()
role = user['role']
cashier_id = user['cashier_id']
st.sidebar.caption(f"{user['username']} | {role}")
if role == 'Cashier':
    st.sidebar.caption(f"Cashier: {db.cashier_name(cashier_id)} ({cashier_id})")
st.sidebar.caption('To log in as a cashier, sign out and enter the cashier account username and password.')
if st.sidebar.button('Sign out'):
    db.logout()
    st.session_state.clear()
    st.rerun()

sections = (['Dashboard', 'Employees', 'Settings & Cashiers', 'Allowances', 'Reports', 'Forecasting', 'Corrections']
            if role == 'Owner/Manager' else
            ['Dashboard', 'Record Service', 'Sell Product', 'Record Expense', 'Sales Register'])
page = st.sidebar.radio('NAVIGATION', sections)
st.sidebar.divider()
st.sidebar.caption('Salon management | Authenticated staff workspace')

st.markdown(f'<div class="hero"><div class="eyebrow"> |  Management suite</div><h1>{escape(salon_name)}</h1><p>Revenue intelligence  |  Staff productivity  |  Cashier accountability</p></div>', unsafe_allow_html=True)

if page == 'Dashboard':
    st.subheader('Business at a glance')
    st.markdown('<div class="goldline"></div>', unsafe_allow_html=True)
    if role == 'Cashier':
        totals = db.cashier_collection_dashboard()
        a,b = st.columns(2)
        c = st.columns(1)[0]
        a.metric('Total collected', fmt(totals['collected']))
        b.metric('Cash', fmt(totals['cash']))
        c.metric('Mobile Money', fmt(totals['mobile_money']))
        st.caption('All-time collections for sales recorded by your cashier account. Total collected = Cash + Mobile Money. Expenses are shown separately below.')
        st.markdown('### My recent sales')
        show_table([row for row in db.sales() if row['cashier_id'] == cashier_id][:10])
    else:
        summary = db.summary()
        a,b = st.columns(2)
        c,d = st.columns(2)
        a.metric('Sales value', fmt(summary.charges))
        b.metric('Payments received', fmt(summary.receipts))
        c.metric('Outstanding', fmt(summary.unpaid_balance()))
        d.metric('Expected wages', fmt(summary.expected_wages))
        st.markdown('### Recent transactions')
        show_table(db.sales()[:10], 'No transactions recorded yet.')
        st.caption('Sales value includes both paid and unpaid charges. Expected wages are not wages paid.')

    activity = db.operating_activity()
    prefix = 'My ' if role == 'Cashier' else ''
    product_card, expense_card = st.columns(2)
    product_card.metric(f'{prefix}product sales value', fmt(activity['product_total']))
    expense_card.metric(f'{prefix}recorded expenses', fmt(activity['expense_total']))
    st.markdown(f'### {prefix}products sold')
    st.caption(f"{len(activity['products'])} product sale records. Values are sales charges, including unpaid sales.")
    show_table(activity['products'], 'No product sales recorded yet.')
    st.markdown(f'### {prefix}expense register')
    show_table(activity['expenses'], 'No expenses recorded yet.')
    if role == 'Cashier':
        st.caption('These product and expense records belong to your cashier account.')

elif page == 'Settings & Cashiers':
    st.subheader('Salon identity & cashier accounts')
    st.markdown('<div class="goldline"></div>', unsafe_allow_html=True)
    with st.form('salon_identity'):
        name = st.text_input('Salon display name', value=salon_name, help='The name shown at the top of your application.')
        if st.form_submit_button('Save salon name'):
            try:
                db.set_salon_name(name)
                st.rerun()
            except (ValueError, sqlite3.Error) as exc:
                st.error(str(exc))
    st.markdown('### Register cashiers')
    with st.form('new_cashier'):
        col1,col2 = st.columns(2)
        with col1: cid = st.text_input('Cashier ID', placeholder='C001')
        with col2: cname = st.text_input('Cashier name', placeholder='e.g. Cashier One')
        if st.form_submit_button('Add cashier'):
            save(lambda: db.add_cashier(cid, cname), 'Cashier registered successfully')
    st.markdown('### Registered cashiers')
    show_table(db.cashiers())
    st.markdown('### Create login account')
    st.caption('Register the cashier above, then create a Cashier login linked to their record. They use the same Sign in page after you sign out.')
    with st.form('account'):
        username = st.text_input('New username')
        password = st.text_input('New password (at least 12 characters)', type='password')
        account_role = st.selectbox('Account role', ['Cashier', 'Owner/Manager'])
        ids = [c['cashier_id'] for c in db.cashiers()]
        cashier_labels = {c['cashier_id']: c['name'] for c in db.cashiers()}
        linked = st.selectbox('Linked cashier (required for Cashier)', [None] + ids, format_func=lambda cid: f'{cashier_labels[cid]} ({cid})' if cid else 'Select cashier')
        if st.form_submit_button('Create account'):
            save(lambda: db.create_account(username, password, account_role, linked))

elif page == 'Employees':
    st.subheader('Employees & wage rates')
    st.markdown('<div class="section-note">Set an expected wage percentage for each employee.</div>', unsafe_allow_html=True)
    with st.form('employee'):
        a,b = st.columns(2)
        with a:
            eid = st.text_input('Employee ID', 'E001')
            name = st.text_input('Full name')
        with b:
            dept = st.selectbox('Department', ['Braiding','Barbering','Hairdressing','Nails','Makeup','Other'])
            rate = st.number_input('Expected wage rate (%)', 0.0,100.0,30.0,1.0)
        if st.form_submit_button('Register employee'):
            save(lambda: db.add_employee(eid,name,dept,rate))
    show_table(db.employees())

elif page == 'Record Service':
    st.subheader('Record a completed service')
    staff=db.employees(active_only=True)
    if cashier_id is None:
        st.info('Ask the Owner/Manager to register a cashier before recording sales.')
    elif not staff:
        st.info('Register employees in the Owner/Manager view first.')
    else:
        with st.form('service'):
            a,b=st.columns(2)
            with a:
                sid=st.text_input('Unique sale ID', f'S{date.today():%Y%m%d}-001')
                dept=st.selectbox('Department',['Braiding','Barbering','Hairdressing','Nails','Makeup','Other'])
                desc=st.text_input('Service style / details', placeholder='Medium knotless braids, waist-length')
            with b:
                price=st.number_input('Agreed client price (UGX)',min_value=1.0,value=50000.0,step=1000.0)
                st.caption('Braiding prices vary by style, length, and agreement; no standard price is imposed.')
            options={f"{x['name']}  |  {x['employee_id']}":x['employee_id'] for x in staff}
            selected=st.multiselect('Employees who worked on this service',list(options))
            allocation=[]
            for key in selected:
                share=st.number_input(f'Contribution (%)  |  {key}',min_value=0.01,max_value=100.0,value=100.0 if len(selected)==1 else 50.0,step=5.0,key=f'share_{key}')
                allocation.append((options[key],share))
            st.caption(f"Allocated: {sum(x[1] for x in allocation):g}% of 100%")
            sale_method = st.selectbox('Payment method', ['Cash', 'Mobile Money'])
            sale_reference = st.text_input('Mobile Money reference', placeholder='Required for Mobile Money')
            st.caption('The full agreed price is received with this sale; no credit sale is created.')
            if st.form_submit_button('Save service sale'):
                save(lambda: db.record_paid_sale(sid,date.today(),'Service',f'{dept}: {desc}',ServiceTransaction(price),allocation,cashier_id=cashier_id,payment=Payment(money(price),sale_method,sale_reference)), 'Service sale and full payment recorded')

elif page == 'Sell Product':
    st.subheader('Sell salon merchandise')
    if cashier_id is None:
        st.info('Register a cashier before recording sales.')
    else:
        with st.form('product'):
            a,b=st.columns(2)
            with a:
                sid=st.text_input('Unique sale ID',f'P{date.today():%Y%m%d}-001')
                desc=st.text_input('Product description',placeholder='Black braids, long pack')
            with b:
                qty=st.number_input('Quantity',1,10000,1)
                unit=st.number_input('Agreed unit price (UGX)',min_value=1.0,value=8000.0,step=500.0)
            st.caption('Products can be entered without a predefined catalogue price.')
            sale_method = st.selectbox('Payment method', ['Cash', 'Mobile Money'])
            sale_reference = st.text_input('Mobile Money reference', placeholder='Required for Mobile Money')
            st.caption('Full payment is recorded with the product sale.')
            if st.form_submit_button('Record product sale'):
                save(lambda: db.record_paid_sale(sid,date.today(),'Product',desc,ProductTransaction(int(qty),unit),cashier_id=cashier_id,payment=Payment(ProductTransaction(int(qty),unit).calculate_total(),sale_method,sale_reference)), 'Product sale and full payment recorded')

elif page == 'Allowances':
    st.subheader('Approve expense allowance')
    with st.form('allowance'):
        amt=st.number_input('Approved amount (UGX)',min_value=1.0,value=50000.0)
        note=st.text_input('Purpose','Operating expenses')
        if st.form_submit_button('Approve allowance'):
            save(lambda: db.approve_allowance(amt,note))
    show_table(db.allowances())

elif page == 'Record Expense':
    st.subheader('Record operating expense')
    allowances=db.allowances()
    if cashier_id is None:
        st.info('Register a cashier before recording expenses.')
    elif not allowances:
        st.info('An Owner/Manager must approve an allowance first.')
    else:
        with st.form('expense'):
            labels={f"#{x['allowance_id']}  |  {fmt(x['amount'])}  |  {x['note']}":x['allowance_id'] for x in allowances}
            chosen=st.selectbox('Approved allowance',list(labels))
            aid=labels[chosen]
            st.caption(f'Remaining: {fmt(db.remaining_allowance(aid))}')
            desc=st.text_input('Expense description')
            amt=st.number_input('Expense amount (UGX)',min_value=1.0,value=5000.0)
            if st.form_submit_button('Record expense'):
                save(lambda: db.add_expense(aid,desc,amt,cashier_id=cashier_id))

elif page == 'Sales Register':
    st.subheader('Sales register')
    if role == 'Cashier':
        with st.expander('Edit my transactions from today'):
            st.caption('Edits close at midnight Kampala time. Older transactions and employee allocation changes require a manager.')
            register = st.selectbox('Transaction type', ['sales', 'payments', 'expenses'])
            editable = db.cashier_editable_records(register)
            record_key = {'sales': 'sale_id', 'payments': 'payment_id', 'expenses': 'expense_id'}[register]
            if editable:
                index = st.selectbox('Transaction to edit', range(len(editable)), format_func=lambda i: f"{editable[i][record_key]} | {fmt(editable[i]['amount'])}")
                record = editable[index]
                with st.form(f'cashier_edit_{register}_{record[record_key]}'):
                    edit_amount = st.text_input('Correct amount (UGX)', value=record['amount'])
                    edits = {'amount': edit_amount}
                    if register == 'payments':
                        edits['method'] = st.selectbox('Correct payment method', ['Cash', 'Mobile Money'], index=['Cash', 'Mobile Money'].index(record['method']))
                        edits['reference'] = st.text_input('Correct reference', value=record['reference'])
                    else:
                        edits['description'] = st.text_input('Correct description', value=record['description'])
                    edit_reason = st.text_area('Reason for edit')
                    if st.form_submit_button('Save same-day correction'):
                        save(lambda: db.correct_transaction(register, record[record_key], edits, edit_reason), 'Correction saved and balances updated.')
            else:
                st.info('No transactions of this type from today are available to edit.')
    st.caption('The cashier column identifies which cashier entered the sale.')
    show_table(db.sales())
    activity = db.operating_activity()
    st.markdown('### Products sold')
    st.metric('Product sales value', fmt(activity['product_total']))
    show_table(activity['products'], 'No product sales recorded yet.')
    st.markdown('### Recorded expenses')
    st.metric('Expense total', fmt(activity['expense_total']))
    show_table(activity['expenses'], 'No expenses recorded yet.')

elif page == 'Reports':
    db.require_manager()
    st.subheader('Download a report')
    report = st.selectbox('Report type', ['Sales', 'Payments', 'Expenses', 'Employee allocations'])
    frequency = st.selectbox('Summary frequency', ['Detailed', 'Daily', 'Weekly', 'Monthly'])
    period = st.selectbox('Date range', ['This month', 'Last 7 days', 'Last 30 days', 'Custom'])
    today = date.today()
    start = today.replace(day=1)
    end = today
    if period == 'Last 7 days':
        start = today - timedelta(days=6)
    elif period == 'Last 30 days':
        start = today - timedelta(days=29)
    elif period == 'Custom':
        left, right = st.columns(2)
        start = left.date_input('From date', value=start)
        end = right.date_input('To date', value=today)
    cashier_choices = {row['cashier_id']: row['name'] for row in db.cashiers()}
    filter_cashier = st.selectbox('Cashier filter', [None] + list(cashier_choices), format_func=lambda cid: f'{cashier_choices[cid]} ({cid})' if cid else 'All cashiers')
    filter_kind = None
    filter_method = None
    if report != 'Expenses':
        filter_kind = st.selectbox('Sale type filter', [None, 'Service', 'Product'], format_func=lambda kind: kind or 'All sale types')
    if report == 'Payments':
        filter_method = st.selectbox('Payment method filter', [None, 'Cash', 'Mobile Money'], format_func=lambda method: method or 'All payment methods')
    st.caption('Dates are inclusive. Sales and employee allocations use the sale date; payments use the payment date; expenses use the expense date. Cashier means the person recorded on that entry.')
    st.caption('Frequency groups the selected results; it does not schedule automatic reports. Weeks start on Monday. Partial weeks and months contain only the selected dates. Amounts in CSV files are UGX.')
    if start > end:
        st.error('From date must not be after To date.')
    else:
        details = db.report_records(report, start, end, filter_cashier, filter_kind, filter_method)
        filtered = summarize_records(details, frequency)
        show_table(filtered, 'No records match these filters.')
        if filtered:
            st.download_button('Download filtered report (CSV)', data=report_csv(filtered),
                               file_name=f"{report.lower().replace(' ', '_')}_{frequency.lower()}_{start}_{end}.csv",
                               mime='text/csv')
    st.divider()
    st.caption('The reconciliation and registers below are all-time salon totals, independent of the download filters above.')
    st.subheader('Revenue reconciliation')
    r=db.summary()
    a,b,c=st.columns(3)
    a.metric('Charged to clients',fmt(r.charges))
    b.metric('Payments received',fmt(r.receipts))
    c.metric('Unpaid balance',fmt(r.unpaid_balance()))
    d,e,f=st.columns(3)
    d.metric('Expenses',fmt(r.expenses))
    e.metric('Expected employee wages',fmt(r.expected_wages))
    f.metric('Net receipts less expenses',fmt(r.net_cash_after_expenses()))
    st.caption('Expected wages are estimates, not wages paid.')
    st.markdown('### Cashier activity')
    show_table(db.cashier_activity(), 'Register cashiers to view activity.')
    st.markdown('### Employee productivity')
    show_table(db.productivity())
    st.markdown('### All sales')
    show_table(db.sales())
    st.markdown('### Payment register')
    show_table(db.payments())
    st.markdown('### Expense register')
    show_table(db.expenses())

elif page == 'Corrections':
    db.require_manager()
    st.subheader('Correct a transaction')
    entity = st.selectbox('Register', ['sales', 'payments', 'expenses'])
    rows = {'sales': db.sales, 'payments': db.payments, 'expenses': db.expenses}[entity]()
    key = {'sales': 'sale_id', 'payments': 'payment_id', 'expenses': 'expense_id'}[entity]
    if rows:
        chosen = st.selectbox('Record', range(len(rows)), format_func=lambda i: f"{rows[i][key]}  |  {fmt(rows[i]['amount'])}")
        row = rows[chosen]
        show_table([row])
        allocations = db.assignments_for_sale(row[key]) if entity == 'sales' else []
        with st.form(f'correction_{entity}_{row[key]}'):
            amount = st.text_input('Corrected total amount (UGX)', value=row['amount'])
            date_key = {'sales': 'sale_date', 'payments': 'paid_on', 'expenses': 'expense_date'}[entity]
            corrected_date = st.date_input('Transaction date', value=date.fromisoformat(row[date_key]))
            cashier_ids = [None] + [c['cashier_id'] for c in db.cashiers()]
            corrected_cashier = st.selectbox('Responsible cashier', cashier_ids, index=cashier_ids.index(row['cashier_id']) if row['cashier_id'] in cashier_ids else 0)
            changes = {'amount': amount, date_key: corrected_date.isoformat(), 'cashier_id': corrected_cashier}
            if entity == 'payments':
                changes['sale_id'] = st.text_input('Sale ID', value=row['sale_id'])
                changes['method'] = st.selectbox('Method', ['Cash', 'Mobile Money'], index=['Cash', 'Mobile Money'].index(row['method']))
                changes['reference'] = st.text_input('Reference', value=row['reference'])
            else:
                changes['description'] = st.text_input('Description', value=row['description'])
            if entity == 'expenses':
                changes['allowance_id'] = st.number_input('Allowance ID', min_value=1, value=row['allowance_id'], step=1)
            if entity == 'sales' and row['kind'] == 'Service':
                allocation_text = st.text_area('Employee allocations (one employee ID,percentage per line)', value='\n'.join(f"{a['employee_id']},{a['share']}" for a in allocations))
                st.caption('Previously assigned employees retain their recorded wage rates. New employees use their current rates.')
            reason = st.text_area('Correction reason (required)')
            if st.form_submit_button('Apply audited correction'):
                def correct():
                    if entity == 'sales' and row['kind'] == 'Service':
                        changes['assignments'] = [tuple(line.split(',')) for line in allocation_text.splitlines() if line.strip()]
                    db.correct_transaction(entity, row[key], changes, reason)
                save(correct, 'Correction saved; reconciliation updated. Reselect the record to review.')
    else:
        st.info('No records to correct.')
    st.markdown('### Correction audit trail')
    show_table(db.audit_log())

elif page == 'Forecasting':
    st.subheader('Seven-day revenue forecast')
    history=db.daily_revenue(28)
    values=[value for _,value in history]
    method=st.radio('Forecasting method',['Moving average','Weekday pattern'],horizontal=True)
    forecaster=MovingAverageForecaster() if method=='Moving average' else WeekdayForecaster()
    forecast=forecaster.forecast(values,7)
    frame=pd.DataFrame({'Date':[date.today()+timedelta(days=i) for i in range(7)],
                        'Forecast UGX':[float(x) for x in forecast]})
    st.bar_chart(frame.set_index('Date'),color='#a43c84')
    st.dataframe(frame,use_container_width=True,hide_index=True)
    st.caption('Illustrative estimates only. Missing days are treated as zero; results are unreliable with limited history.')
