"""Saloon Management System: customizable coursework demonstration.

Run: python -m streamlit run app.py
Demo role selection and cashier names are NOT secure authentication.
"""
from datetime import date
import sqlite3
from html import escape

import pandas as pd
import streamlit as st

from salon_core import (
    SalonDatabase, Payment, ProductTransaction, ServiceTransaction,
    MovingAverageForecaster, WeekdayForecaster, money,
)

st.set_page_config(page_title="Salon Studio | Management", page_icon="✦", layout="wide", initial_sidebar_state="expanded")

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
.hero:before {content:'✦';font-size:150px;position:absolute;right:32px;top:-65px;color:#d5a84930;}
.hero .eyebrow {letter-spacing:.2em;text-transform:uppercase;font-size:11px;color:#f6c87e;font-weight:700;}
.hero h1 {color:white !important;font-size:2.15rem !important;margin:.25rem 0;}
.hero p {color:#f5dfea;margin:0;font-size:14px;}
.section-note {color:#836c86;font-size:13px;margin-top:-5px;margin-bottom:18px;}
.goldline {width:46px;height:3px;background:#d5a849;border-radius:10px;margin:8px 0 18px;}
.brand {font-family:Georgia,serif;font-size:26px;font-weight:bold;color:#ffe9f5;text-align:center;line-height:1.2;margin:18px 0 2px;}
.brand-sub {font-size:11px;letter-spacing:.2em;text-align:center;color:#f2bb72;margin-bottom:25px;}
[data-testid="stSidebar"] hr {border-color:#ffffff26;}
</style>""", unsafe_allow_html=True)


def fmt(value):
    return f"UGX {money(value):,.0f}"


def save(action, message="Saved successfully"):
    try:
        result = action()
        st.success(message)
        return result
    except (ValueError, TypeError, sqlite3.Error) as exc:
        st.error(str(exc))
        return None


def show_table(rows, empty="No records yet"):
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty)


db = SalonDatabase()
salon_name = db.salon_name()
st.sidebar.markdown(f'<div class="brand">✦ {escape(salon_name)}</div><div class="brand-sub">BEAUTY • BUSINESS • INSIGHTS</div>', unsafe_allow_html=True)
role = st.sidebar.radio('VIEW AS', ['Cashier', 'Owner/Manager'])
cashiers = db.cashiers(active_only=True)
cashier_id = None
if role == 'Cashier':
    if cashiers:
        choices = {f"{c['name']} · {c['cashier_id']}": c['cashier_id'] for c in cashiers}
        cashier_id = choices[st.sidebar.selectbox('CASHIER ON DUTY', list(choices))]
        st.sidebar.caption('Transactions will be recorded against this cashier.')
    else:
        st.sidebar.warning('No cashier registered. Switch to Owner/Manager → Settings & Cashiers to add one.')

sections = (['Dashboard', 'Employees', 'Settings & Cashiers', 'Allowances', 'Reports', 'Forecasting']
            if role == 'Owner/Manager' else
            ['Dashboard', 'Record Service', 'Sell Product', 'Receive Payment', 'Record Expense', 'Sales Register'])
page = st.sidebar.radio('NAVIGATION', sections)
st.sidebar.divider()
st.sidebar.caption('CSC8101 · Classroom demonstration only. Role switching is not authentication; use test records.')

st.markdown(f'<div class="hero"><div class="eyebrow">✦ Management suite</div><h1>{__import__("html").escape(salon_name)}</h1><p>Revenue intelligence · Staff productivity · Cashier accountability</p></div>', unsafe_allow_html=True)

if page == 'Dashboard':
    st.subheader('Business at a glance')
    st.markdown('<div class="goldline"></div>', unsafe_allow_html=True)
    summary = db.summary()
    a,b,c,d = st.columns(4)
    a.metric('Sales value', fmt(summary.charges))
    b.metric('Payments received', fmt(summary.receipts))
    c.metric('Outstanding', fmt(summary.unpaid_balance()))
    d.metric('Expected wages', fmt(summary.expected_wages))
    st.markdown('### Recent transactions')
    show_table(db.sales()[:10], 'No transactions recorded yet.')
    st.caption('Sales value includes both paid and unpaid charges. Expected wages are not wages paid.')

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
    st.info('Cashier names identify who recorded each transaction. For actual deployment, secure login and passwords must be added.')

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
            options={f"{x['name']} · {x['employee_id']}":x['employee_id'] for x in staff}
            selected=st.multiselect('Employees who worked on this service',list(options))
            allocation=[]
            for key in selected:
                share=st.number_input(f'Contribution (%) — {key}',min_value=0.01,max_value=100.0,value=100.0 if len(selected)==1 else 50.0,step=5.0,key=f'share_{key}')
                allocation.append((options[key],share))
            st.caption(f"Allocated: {sum(x[1] for x in allocation):g}% of 100%")
            if st.form_submit_button('Save service sale'):
                save(lambda: db.record_sale(sid,date.today(),'Service',f'{dept}: {desc}',ServiceTransaction(price),allocation,cashier_id=cashier_id))

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
            if st.form_submit_button('Record product sale'):
                save(lambda: db.record_sale(sid,date.today(),'Product',desc,ProductTransaction(int(qty),unit),cashier_id=cashier_id))

elif page == 'Receive Payment':
    st.subheader('Receive payment')
    sales=db.sales()
    if cashier_id is None:
        st.info('Register a cashier before recording payments.')
    elif not sales:
        st.info('Record a service or product sale first.')
    else:
        with st.form('payment'):
            labels={f"{x['sale_id']} · {x['description']} · {fmt(x['amount'])}":x['sale_id'] for x in sales}
            chosen=st.selectbox('Select sale',list(labels))
            a,b=st.columns(2)
            with a:
                amt=st.number_input('Amount received (UGX)',min_value=1.0,value=10000.0)
            with b:
                method=st.selectbox('Payment method',['Cash','Mobile Money'])
            ref=st.text_input('Mobile Money reference',placeholder='Required for Mobile Money')
            if st.form_submit_button('Record payment'):
                save(lambda: db.add_payment(labels[chosen],Payment(money(amt),method,ref),cashier_id=cashier_id))

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
            labels={f"#{x['allowance_id']} · {fmt(x['amount'])} · {x['note']}":x['allowance_id'] for x in allowances}
            chosen=st.selectbox('Approved allowance',list(labels))
            aid=labels[chosen]
            st.caption(f'Remaining: {fmt(db.remaining_allowance(aid))}')
            desc=st.text_input('Expense description')
            amt=st.number_input('Expense amount (UGX)',min_value=1.0,value=5000.0)
            if st.form_submit_button('Record expense'):
                save(lambda: db.add_expense(aid,desc,amt,cashier_id=cashier_id))

elif page == 'Sales Register':
    st.subheader('Sales register')
    st.caption('The cashier column identifies which cashier entered the sale.')
    show_table(db.sales())

elif page == 'Reports':
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
    st.caption('Expected wages are estimates, not wages paid. Demo data only.')
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

elif page == 'Forecasting':
    st.subheader('Seven-day revenue forecast')
    history=db.daily_revenue(28)
    values=[value for _,value in history]
    method=st.radio('Forecasting method',['Moving average','Weekday pattern'],horizontal=True)
    forecaster=MovingAverageForecaster() if method=='Moving average' else WeekdayForecaster()
    forecast=forecaster.forecast(values,7)
    frame=pd.DataFrame({'Date':[date.today()+pd.Timedelta(days=i) for i in range(1,8)],
                        'Forecast UGX':[float(x) for x in forecast]})
    st.bar_chart(frame.set_index('Date'),color='#a43c84')
    st.dataframe(frame,use_container_width=True,hide_index=True)
    st.caption('Illustrative estimates only. Missing days are treated as zero; results are unreliable with limited history.')
