"""Saloon Management System — working Streamlit coursework prototype.

RUN: python -m streamlit run app.py
Demo access only: this is not production authentication.
"""
from datetime import date
from decimal import Decimal
import sqlite3
import pandas as pd
import streamlit as st

from salon_core import (
    SalonDatabase, Payment, ProductTransaction, ServiceTransaction,
    MovingAverageForecaster, WeekdayForecaster, money,
)

st.set_page_config(page_title='Saloon Management System', page_icon='✂️', layout='wide')
st.title('✂️ Saloon Management System')
st.caption('Salon revenue reconciliation • employee productivity • expected wages • forecasting')
st.warning('Coursework demonstration: role selection below is not secure authentication. Use illustrative data only.', icon='⚠️')
db = SalonDatabase()

role = st.sidebar.radio('Demo role', ['Owner/Manager', 'Cashier'])
st.sidebar.caption('Cashier enters sales and payments. Owner/Manager oversees staff, allowances, reports and forecasts.')

sections = (['Employees', 'Allowances', 'Reports', 'Forecasting'] if role == 'Owner/Manager'
            else ['Record Service', 'Sell Product', 'Receive Payment', 'Record Expense', 'Sales Register'])
page = st.sidebar.radio('Menu', sections)

def display_error(callable_fn):
    try:
        result = callable_fn()
        st.success('Saved successfully')
        return result
    except (ValueError, sqlite3.IntegrityError, TypeError) as exc:
        st.error(str(exc))
        return None

def fmt(value):
    return f'UGX {money(value):,.0f}'

if page == 'Employees':
    st.subheader('Register employees and wage rates')
    with st.form('employee'):
        eid = st.text_input('Employee ID', 'E001')
        name = st.text_input('Full name')
        dept = st.selectbox('Department', ['Braiding', 'Barbering', 'Hairdressing', 'Nails', 'Makeup', 'Other'])
        rate = st.number_input('Expected wage rate (%)', 0.0, 100.0, 30.0, 1.0)
        if st.form_submit_button('Register employee'):
            display_error(lambda: db.add_employee(eid, name, dept, rate))
    st.dataframe(db.employees(), use_container_width=True)

elif page == 'Record Service':
    st.subheader('Record a completed service')
    staff = db.employees(active_only=True)
    if not staff:
        st.info('An Owner/Manager must register employees before services can be recorded.')
    else:
        with st.form('service'):
            sale_id = st.text_input('Sale ID', f'S{date.today():%Y%m%d}-001')
            dept = st.selectbox('Department', ['Braiding', 'Barbering', 'Hairdressing', 'Nails', 'Makeup', 'Other'])
            desc = st.text_input('Service details (e.g. medium knotless braids, waist-length)')
            price = st.number_input('Agreed client price (UGX)', min_value=1.0, value=50000.0, step=1000.0)
            st.caption('For braiding and other custom services, enter the actual agreed price. No standard price is imposed.')
            selected = st.multiselect('Participating employees', [f"{x['employee_id']} — {x['name']}" for x in staff])
            percentages = []
            for option in selected:
                share = st.number_input(f'Contribution share (%) for {option}', min_value=0.01, max_value=100.0,
                                        value=100.0 if len(selected)==1 else 50.0, step=5.0, key=option)
                percentages.append((option.split(' — ')[0], share))
            st.caption(f'Total assigned: {sum(x[1] for x in percentages):g}% (must equal 100%)')
            if st.form_submit_button('Save service sale'):
                display_error(lambda: db.record_sale(sale_id, date.today(), 'Service', f'{dept}: {desc}',
                                                    ServiceTransaction(price), percentages))

elif page == 'Sell Product':
    st.subheader('Sell salon merchandise')
    with st.form('product'):
        sale_id = st.text_input('Sale ID', f'P{date.today():%Y%m%d}-001')
        desc = st.text_input('Product description (e.g. black braids, long pack)')
        qty = st.number_input('Quantity', 1, 10000, 1)
        price = st.number_input('Agreed selling price per item (UGX)', min_value=1.0, value=8000.0, step=500.0)
        st.caption('The product need not be pre-registered. This records one product line.')
        if st.form_submit_button('Save product sale'):
            display_error(lambda: db.record_sale(sale_id, date.today(), 'Product', desc,
                                                  ProductTransaction(int(qty), price)))

elif page == 'Receive Payment':
    st.subheader('Receive a client payment')
    sales = db.sales()
    if not sales:
        st.info('Record a sale first.')
    else:
        with st.form('payment'):
            sale = st.selectbox('Sale', [f"{s['sale_id']} — {s['description']} ({fmt(s['amount'])})" for s in sales])
            amount = st.number_input('Amount received (UGX)', min_value=1.0, value=10000.0)
            method = st.selectbox('Payment method', ['Cash', 'Mobile Money'])
            reference = st.text_input('Mobile Money transaction reference (required for Mobile Money)')
            if st.form_submit_button('Record payment'):
                sale_id = sale.split(' — ')[0]
                display_error(lambda: db.add_payment(sale_id, Payment(money(amount), method, reference)))

elif page == 'Allowances':
    st.subheader('Approve cashier expense allowance')
    with st.form('allowance'):
        amt = st.number_input('Approved amount (UGX)', min_value=1.0, value=50000.0)
        note = st.text_input('Approval note', 'Operating expenses')
        if st.form_submit_button('Approve allowance'):
            display_error(lambda: db.approve_allowance(amt, note))
    st.dataframe(db.allowances(), use_container_width=True)

elif page == 'Record Expense':
    st.subheader('Record an expense against approved allowance')
    allowances = db.allowances()
    if not allowances:
        st.info('Owner/Manager must first approve an allowance.')
    else:
        with st.form('expense'):
            option = st.selectbox('Approved allowance', [f"{x['allowance_id']} — {fmt(x['amount'])} ({x['note']})" for x in allowances])
            aid = int(option.split(' — ')[0])
            st.caption(f'Remaining allowance: {fmt(db.remaining_allowance(aid))}')
            desc = st.text_input('Expense description')
            amt = st.number_input('Expense amount (UGX)', min_value=1.0, value=5000.0)
            if st.form_submit_button('Record expense'):
                display_error(lambda: db.add_expense(aid, desc, amt))

elif page == 'Sales Register':
    st.subheader('Recorded service and product sales')
    st.dataframe(db.sales(), use_container_width=True)

elif page == 'Reports':
    st.subheader('Revenue reconciliation')
    r = db.summary()
    a,b,c = st.columns(3)
    a.metric('Service and product charges', fmt(r.charges))
    b.metric('Client receipts', fmt(r.receipts))
    c.metric('Unpaid balance', fmt(r.unpaid_balance()))
    d,e,f = st.columns(3)
    d.metric('Recorded expenses', fmt(r.expenses))
    e.metric('Expected wages', fmt(r.expected_wages))
    f.metric('Receipts less expenses', fmt(r.net_cash_after_expenses()))
    st.caption('Expected wages are estimates, not wages paid. Unpaid balance is charges minus receipts; no adjustments or refunds are modelled yet.')
    st.subheader('Employee productivity')
    st.dataframe(db.productivity(), use_container_width=True)
    st.subheader('Sales register')
    st.dataframe(db.sales(), use_container_width=True)

elif page == 'Forecasting':
    st.subheader('Seven-day revenue forecast')
    history = db.daily_revenue(28)
    data = [total for _, total in history]
    model = st.radio('Simple forecasting approach', ['Moving average', 'Weekday pattern'], horizontal=True)
    forecaster = MovingAverageForecaster() if model == 'Moving average' else WeekdayForecaster()
    forecast = forecaster.forecast(data, 7)
    frame = pd.DataFrame({'Date': [date.today() + pd.Timedelta(days=i) for i in range(1,8)],
                          'Forecast UGX': [float(x) for x in forecast]})
    st.dataframe(frame, use_container_width=True)
    st.bar_chart(frame.set_index('Date'))
    st.caption('Illustrative forecast from 28 recent calendar days. Missing days are treated as zero; limited history makes forecasts unreliable.')
