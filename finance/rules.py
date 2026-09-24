"""
Simple keyword rules for Pass 1 financial categorization.
Each rule defines a target category name and matching keywords.
Any transaction matching a rule is assigned confidence = 1.0.
"""

KEYWORD_RULES = [
    # Revenue (P&L)
    ('Food Sales', [
        'food sales',
        'refunds and discounts',
    ]),
    ('Beverage Sales', [
        'beverage sales',
    ]),
    ('Catering Revenue', [
        'catering invoice',
        'corporate catering',
    ]),
    ('Delivery App Payouts', [
        'delivery marketplace payout',
    ]),

    # Cost of Goods Sold (P&L)
    ('Food Inventory', [
        'food inventory purchase',
        'sysco',
        'us foods',
        'butcher & sons',
        'local produce',
        'bakery supply',
    ]),
    ('Beverage Inventory', [
        'beverage inventory purchase',
        'southern glazer',
        'craft beer distributor',
        'beverage depot',
    ]),
    ('Kitchen & Packaging Supplies', [
        'to-go packaging',
        'packaging and disposables',
        'restaurant depot',
        'cleaning and linen service',
        'linenpro',
    ]),

    # Payroll (P&L)
    ('Kitchen Wages', [
        'payroll - hourly kitchen and foh',
        'kitchen wages',
    ]),
    ('Salaries & Management', [
        'manager salary payroll',
    ]),
    ('Payroll Taxes & Benefits', [
        'payroll taxes and benefits',
    ]),

    # Operating Expenses (P&L)
    ('Rent & Occupancy', [
        'rent - landlord',
    ]),
    ('Utilities', [
        'utilities - electric/gas/water',
        'city utilities',
    ]),
    ('Software & POS Subscriptions', [
        'pos/software subscription',
    ]),
    ('Insurance', [
        'insurance premium',
        'next insurance',
    ]),
    ('Accounting & Legal', [
        'accounting/bookkeeping',
        'ledgerpro',
    ]),
    ('Repairs & Maintenance', [
        'repairs and maintenance',
        'kitchen repair co',
    ]),
    ('Merchant Processing Fees', [
        'delivery platform commission',
    ]),

    # Non-P&L (Balance Sheet / Transfers)
    ('Loan Repayment', [
        'loan principal repayment',
    ]),
    ('Owner Withdrawal', [
        'owner distribution',
    ]),
    ('Tax Payment', [
        'sales tax remittance',
    ]),
    ('Equipment Purchase', [
        'equipment purchase - new oven',
    ]),
]


def match_keyword_rule(description: str) -> str | None:
    """
    Checks transaction description against keyword rules.
    Returns category name if matched, or None if no rule matches.
    """
    desc_lower = description.lower()
    for category_name, keywords in KEYWORD_RULES:
        for kw in keywords:
            if kw.lower() in desc_lower:
                return category_name
    return None
