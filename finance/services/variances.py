import json
import os
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, List
from collections import defaultdict
from dotenv import load_dotenv

from finance.models import Transaction, Category
from finance.services.pnl import calculate_monthly_pnl

load_dotenv()

# ==============================================================================
# CONFIGURABLE MATERIALITY THRESHOLDS (Rule: make both configurable at top)
# ==============================================================================
PERCENT_THRESHOLD = Decimal('10.0')     # Minimum percentage change (e.g. 10%)
ABSOLUTE_THRESHOLD = Decimal('2000.00') # Minimum dollar change (e.g. $2,000.00)


def get_driver_categories(line_key: str, m1: str, m2: str) -> List[Dict[str, Any]]:
    """
    Finds the categories with the largest absolute change between m1 and m2
    for a given P&L line item using pure Python/SQL.
    """
    y1, mon1 = map(int, m1.split('-'))
    y2, mon2 = map(int, m2.split('-'))

    # Determine category types associated with this line
    type_map = {
        'revenue': ['revenue'],
        'cogs': ['cogs'],
        'gross_profit': ['revenue', 'cogs'],
        'payroll': ['payroll'],
        'opex': ['opex'],
        'operating_profit': ['revenue', 'cogs', 'payroll', 'opex'],
    }
    target_types = type_map.get(line_key, [])

    txs_m1 = Transaction.objects.filter(
        in_pnl=True, date__year=y1, date__month=mon1, category__type__in=target_types
    ).select_related('category')

    txs_m2 = Transaction.objects.filter(
        in_pnl=True, date__year=y2, date__month=mon2, category__type__in=target_types
    ).select_related('category')

    cat_m1 = defaultdict(lambda: Decimal('0.00'))
    cat_m2 = defaultdict(lambda: Decimal('0.00'))

    for tx in txs_m1:
        if tx.category:
            # Costs are shown as positive magnitudes; revenue is positive
            val = tx.amount if tx.category.type == 'revenue' else abs(tx.amount)
            cat_m1[tx.category.name] += val

    for tx in txs_m2:
        if tx.category:
            val = tx.amount if tx.category.type == 'revenue' else abs(tx.amount)
            cat_m2[tx.category.name] += val

    all_cats = set(cat_m1.keys()) | set(cat_m2.keys())
    category_changes = []

    for name in all_cats:
        v1 = cat_m1[name].quantize(Decimal('0.01'))
        v2 = cat_m2[name].quantize(Decimal('0.01'))
        diff = (v2 - v1).quantize(Decimal('0.01'))
        category_changes.append({
            'category': name,
            'prior_amount': float(v1),
            'current_amount': float(v2),
            'dollar_change': float(diff),
            'abs_change': float(abs(diff)),
            'direction': 'increased' if diff > 0 else 'decreased'
        })

    # Sort categories by absolute change descending
    category_changes.sort(key=lambda x: x['abs_change'], reverse=True)
    return category_changes[:3]


def get_top_driver_transactions(line_key: str, m2: str) -> List[Dict[str, Any]]:
    """
    Finds the top 5 transactions that drove the figure in m2.
    """
    y2, mon2 = map(int, m2.split('-'))

    type_map = {
        'revenue': ['revenue'],
        'cogs': ['cogs'],
        'gross_profit': ['revenue', 'cogs'],
        'payroll': ['payroll'],
        'opex': ['opex'],
        'operating_profit': ['revenue', 'cogs', 'payroll', 'opex'],
    }
    target_types = type_map.get(line_key, [])

    txs = Transaction.objects.filter(
        in_pnl=True, date__year=y2, date__month=mon2, category__type__in=target_types
    ).select_related('category')

    # Sort by absolute amount descending to find the largest single contributors
    sorted_txs = sorted(txs, key=lambda tx: abs(tx.amount), reverse=True)[:5]

    return [
        {
            'date': tx.date.strftime('%Y-%m-%d'),
            'description': tx.description,
            'amount': float(abs(tx.amount)),
            'category': tx.category.name if tx.category else 'Uncategorized',
        }
        for tx in sorted_txs
    ]


def find_material_variances() -> List[Dict[str, Any]]:
    """
    Detects material variances between consecutive months using plain code only.
    A change is material if |pct_change| >= PERCENT_THRESHOLD AND |dollar_change| >= ABSOLUTE_THRESHOLD.
    Returns structured data for each variance.
    """
    pnl = calculate_monthly_pnl()
    months = pnl['months']
    lines = pnl['lines']

    variances = []

    for i in range(len(months) - 1):
        m1, m2 = months[i], months[i + 1]
        m1_label = datetime.strptime(m1, '%Y-%m').strftime('%b %Y')
        m2_label = datetime.strptime(m2, '%Y-%m').strftime('%b %Y')

        for line in lines:
            v1 = line['values'][m1]
            v2 = line['values'][m2]
            delta = (v2 - v1).quantize(Decimal('0.01'))
            abs_delta = abs(delta)

            # Calculate percentage change
            if v1 != Decimal('0.00'):
                pct_change = (abs_delta / abs(v1) * Decimal('100.0')).quantize(Decimal('0.1'))
            else:
                pct_change = Decimal('100.0') if abs_delta > 0 else Decimal('0.0')

            # Materiality condition: more than 10% AND more than absolute amount
            if pct_change >= PERCENT_THRESHOLD and abs_delta >= ABSOLUTE_THRESHOLD:
                line_key = line['key']
                driver_categories = get_driver_categories(line_key, m1, m2)
                top_txs = get_top_driver_transactions(line_key, m2)

                # Build drill-down URL
                dtype = line['drilldown_type']
                if dtype == 'pnl_all':
                    drilldown_url = f"/transactions/?month={m2}&in_pnl=true"
                else:
                    drilldown_url = f"/transactions/?month={m2}&type={dtype}"

                variance_item = {
                    'id': f"{line_key}_{m1}_{m2}",
                    'line_key': line_key,
                    'line_label': line['label'],
                    'from_month': m1,
                    'to_month': m2,
                    'from_month_label': m1_label,
                    'to_month_label': m2_label,
                    'prior_amount': float(v1),
                    'current_amount': float(v2),
                    'dollar_change': float(delta),
                    'abs_dollar_change': float(abs_delta),
                    'pct_change': float(pct_change),
                    'direction': 'increased' if delta > 0 else 'decreased',
                    'driver_categories': driver_categories,
                    'top_transactions': top_txs,
                    'view_transactions_url': drilldown_url,
                }
                variances.append(variance_item)

    return variances


def explain_variance_with_llm(variance_data: Dict[str, Any]) -> str:
    """
    Sends ONLY the structured variance data to the LLM.
    Enforces a strict 2-3 sentence plain-English explanation without adding unauthorized numbers.
    """
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')

    prompt = f"""You are a corporate controller and financial analyst.
Explain the following monthly material variance in 2 to 3 concise, professional plain-English sentences.

STRICT CONSTRAINTS:
1. You must NOT calculate or alter any numbers.
2. You must NOT invent, guess, or mention any number, dollar amount, or percentage that is NOT explicitly provided in the data below.
3. Identify the primary driver categories and notable vendor transactions from the data that caused this change.

STRUCTURED VARIANCE DATA:
{json.dumps(variance_data, indent=2)}

EXPLANATION (2-3 sentences only):"""

    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config={'temperature': 0.1}
            )
            explanation = response.text.strip()
            if explanation:
                return explanation
        except Exception as e:
            print(f"Notice: Gemini API call failed ({e}). Using deterministic explanation.")

    # High-quality deterministic explanation if API key is not configured or offline
    direction = variance_data['direction']
    line = variance_data['line_label']
    m1 = variance_data['from_month_label']
    m2 = variance_data['to_month_label']
    change = abs(variance_data['dollar_change'])
    pct = variance_data['pct_change']

    top_cat = variance_data['driver_categories'][0]['category'] if variance_data['driver_categories'] else 'operations'
    top_tx = variance_data['top_transactions'][0]['description'] if variance_data['top_transactions'] else 'underlying activity'

    return (
        f"{line} {direction} by ${change:,.2f} ({pct}%) from {m1} to {m2}. "
        f"This shift was primarily driven by changes in {top_cat}, "
        f"with significant activity including '{top_tx}'."
    )


def get_variances_with_explanations() -> List[Dict[str, Any]]:
    """
    Finds all material variances and attaches the LLM explanation to each.
    """
    variances = find_material_variances()
    for var in variances:
        var['explanation'] = explain_variance_with_llm(var)
    return variances
