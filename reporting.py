"""Small helpers for report summaries and spreadsheet-safe CSV downloads."""
import csv
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from salon_core import money


def summarize_records(rows, frequency):
    if frequency == 'Detailed':
        return rows
    if frequency not in ('Daily', 'Weekly', 'Monthly'):
        raise ValueError('Unknown report frequency')
    groups = {}
    for row in rows:
        day = date.fromisoformat(row['date'])
        if frequency == 'Weekly':
            day -= timedelta(days=day.weekday())
        elif frequency == 'Monthly':
            day = day.replace(day=1)
        key = day.isoformat()
        if key not in groups:
            groups[key] = {'period_start': key, 'records': 0, 'amount': Decimal(0)}
            if 'expected_wages' in row:
                groups[key]['expected_wages'] = Decimal(0)
        group = groups[key]
        group['records'] += 1
        group['amount'] += money(row['amount'])
        if 'expected_wages' in row:
            group['expected_wages'] += money(row['expected_wages'])
    return [groups[key] for key in sorted(groups)]


def report_csv(rows):
    if not rows:
        return b''
    output = StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        safe_row = {}
        for key, value in row.items():
            if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
                value = "'" + value
            safe_row[key] = value
        writer.writerow(safe_row)
    return output.getvalue().encode('utf-8-sig')
