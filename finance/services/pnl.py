from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, List
from django.db.models import Sum
from finance.models import Transaction, Category


def calculate_monthly_pnl() -> Dict[str, Any]:
    """
    Computes monthly Profit & Loss figures using pure Python and SQL.
    Strictly deterministic financial math (Rule 1 & Rule 4). NO LLM.

    Sign Handling Convention:
    - In raw bank data: Revenue is positive (credits); expenses are negative (debits).
    - In this P&L presentation: Costs (COGS, Payroll, Opex) are shown as POSITIVE numbers.
    - Gross Profit is calculated as: Revenue - COGS
    - Operating Profit is calculated as: Gross Profit - Payroll - Operating Expenses
    """
    # Only include transactions where in_pnl = True
    pnl_txs = Transaction.objects.filter(in_pnl=True).select_related('category')

    # Identify all distinct months sorted chronologically
    date_entries = pnl_txs.dates('date', 'month', order='ASC')
    months = [d.strftime('%Y-%m') for d in date_entries]
    month_labels = [datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in months]

    # Initialize monthly accumulators for each category type using Decimal
    # Types: revenue, cogs, payroll, opex
    monthly_data = {
        m: {
            'revenue': Decimal('0.00'),
            'cogs': Decimal('0.00'),
            'payroll': Decimal('0.00'),
            'opex': Decimal('0.00'),
        }
        for m in months
    }

    # Aggregate by month and category type
    for tx in pnl_txs:
        m = tx.date.strftime('%Y-%m')
        if not tx.category:
            continue
        ctype = tx.category.type
        if ctype in monthly_data[m]:
            monthly_data[m][ctype] += tx.amount

    # Build P&L line items
    # Show costs as positive numbers (abs value)
    pnl_lines = [
        {
            'key': 'revenue',
            'label': 'Revenue',
            'is_total': False,
            'drilldown_type': 'revenue',
            'values': {},
            'total': Decimal('0.00'),
        },
        {
            'key': 'cogs',
            'label': 'Cost of Goods Sold (COGS)',
            'is_total': False,
            'drilldown_type': 'cogs',
            'values': {},
            'total': Decimal('0.00'),
        },
        {
            'key': 'gross_profit',
            'label': 'Gross Profit',
            'is_total': True,
            'drilldown_type': 'revenue,cogs',
            'formula': 'Revenue − COGS',
            'values': {},
            'total': Decimal('0.00'),
        },
        {
            'key': 'payroll',
            'label': 'Payroll',
            'is_total': False,
            'drilldown_type': 'payroll',
            'values': {},
            'total': Decimal('0.00'),
        },
        {
            'key': 'opex',
            'label': 'Operating Expenses (Opex)',
            'is_total': False,
            'drilldown_type': 'opex',
            'values': {},
            'total': Decimal('0.00'),
        },
        {
            'key': 'operating_profit',
            'label': 'Operating Profit',
            'is_total': True,
            'drilldown_type': 'pnl_all',
            'formula': 'Gross Profit − Payroll − Opex',
            'values': {},
            'total': Decimal('0.00'),
        },
    ]

    # Map line dictionary by key for easy population
    lines_by_key = {line['key']: line for line in pnl_lines}

    # Populate monthly values and calculated totals
    for m in months:
        data = monthly_data[m]
        
        # Revenue is already positive (or contra-revenue reduces it)
        rev = data['revenue'].quantize(Decimal('0.01'))
        
        # Costs are negative in DB; convert to positive numbers for presentation
        cogs = abs(data['cogs']).quantize(Decimal('0.01'))
        payroll = abs(data['payroll']).quantize(Decimal('0.01'))
        opex = abs(data['opex']).quantize(Decimal('0.01'))

        # Calculations
        gross_profit = (rev - cogs).quantize(Decimal('0.01'))
        operating_profit = (gross_profit - payroll - opex).quantize(Decimal('0.01'))

        # Store in row structures
        lines_by_key['revenue']['values'][m] = rev
        lines_by_key['cogs']['values'][m] = cogs
        lines_by_key['gross_profit']['values'][m] = gross_profit
        lines_by_key['payroll']['values'][m] = payroll
        lines_by_key['opex']['values'][m] = opex
        lines_by_key['operating_profit']['values'][m] = operating_profit

    # Compute Total column (sum across all months)
    for line in pnl_lines:
        line['total'] = sum(line['values'].values(), Decimal('0.00')).quantize(Decimal('0.01'))

    return {
        'months': months,
        'month_labels': list(zip(months, month_labels)),
        'lines': pnl_lines,
        'sign_convention': (
            "Costs (COGS, Payroll, Opex) are displayed as positive numbers. "
            "Gross Profit = Revenue − COGS. "
            "Operating Profit = Gross Profit − Payroll − Operating Expenses."
        ),
    }
