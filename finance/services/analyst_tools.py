import re
from decimal import Decimal
from typing import Dict, Any, List, Optional
from finance.models import Transaction, Category
from finance.services.pnl import calculate_monthly_pnl
from finance.services.variances import find_material_variances
from finance.services.review_detector import detect_review_items


def normalize_month_input(month_str: Optional[str]) -> Optional[str]:
    """
    Normalizes month strings (e.g. 'March', 'mar', '03', '2026-03') into 'YYYY-MM' format.
    Defaults to 2026 if year is omitted.
    """
    if not month_str:
        return None
    cleaned = str(month_str).strip().lower()

    # 1. Match YYYY-MM explicitly first
    match = re.search(r'202\d-\d{2}', cleaned)
    if match:
        return match.group(0)

    # 2. Check month names and numbers
    if 'jan' in cleaned or cleaned in ('1', '01'):
        return '2026-01'
    if 'feb' in cleaned or cleaned in ('2', '02'):
        return '2026-02'
    if 'mar' in cleaned or cleaned in ('3', '03'):
        return '2026-03'

    return None


def get_pnl(month: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves Profit & Loss figures calculated strictly via Python/SQL.
    If a month is provided (e.g. '2026-03' or 'March'), returns figures for that month.
    Otherwise returns all months.
    """
    pnl = calculate_monthly_pnl()
    norm_month = normalize_month_input(month)

    if norm_month:
        if norm_month not in pnl['months']:
            return {
                'error': f"Month '{month}' (resolved to {norm_month}) not found. Available months: {pnl['months']}"
            }
        
        # Filter for single month
        lines_data = {}
        for line in pnl['lines']:
            lines_data[line['label']] = {
                'amount': f"${line['values'].get(norm_month, Decimal('0.00')):,.2f}",
                'raw_decimal': float(line['values'].get(norm_month, Decimal('0.00'))),
                'drilldown_url': f"/transactions/?month={norm_month}&type={line['drilldown_type']}",
            }

        return {
            'month': norm_month,
            'line_items': lines_data,
            'accounting_notes': pnl['sign_convention']
        }

    # Return all months
    all_summary = {}
    for line in pnl['lines']:
        all_summary[line['label']] = {
            m: f"${line['values'][m]:,.2f}" for m in pnl['months']
        }
        all_summary[line['label']]['Total'] = f"${line['total']:,.2f}"

    return {
        'months': pnl['months'],
        'summary': all_summary,
        'accounting_notes': pnl['sign_convention']
    }


def compare_months(month_a: str, month_b: str) -> Dict[str, Any]:
    """
    Compares P&L lines between two consecutive or specified months.
    Computes dollar variance and percentage changes using deterministic code.
    """
    pnl = calculate_monthly_pnl()
    m_a = normalize_month_input(month_a)
    m_b = normalize_month_input(month_b)

    if not m_a or m_a not in pnl['months']:
        return {'error': f"Invalid first month '{month_a}'. Available: {pnl['months']}"}
    if not m_b or m_b not in pnl['months']:
        return {'error': f"Invalid second month '{month_b}'. Available: {pnl['months']}"}

    comparisons = {}
    for line in pnl['lines']:
        v_a = line['values'].get(m_a, Decimal('0.00'))
        v_b = line['values'].get(m_b, Decimal('0.00'))
        diff = v_b - v_a
        pct = (abs(diff) / abs(v_a) * 100) if v_a != Decimal('0.00') else Decimal('0.0')

        comparisons[line['label']] = {
            m_a: f"${v_a:,.2f}",
            m_b: f"${v_b:,.2f}",
            'dollar_change': f"${diff:+,.2f}",
            'percentage_change': f"{pct:.1f}%",
            'direction': 'increased' if diff > 0 else ('decreased' if diff < 0 else 'unchanged'),
            'drilldown_url': f"/transactions/?month={m_b}&type={line['drilldown_type']}"
        }

    return {
        'from_month': m_a,
        'to_month': m_b,
        'comparisons': comparisons
    }


def get_transactions(
    category: Optional[str] = None,
    month: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Retrieves transactions from the database matching category or month filters.
    Includes transaction IDs, dates, descriptions, amounts, and source row references.
    """
    qs = Transaction.objects.filter(in_pnl=True).select_related('category')

    norm_month = normalize_month_input(month)
    if norm_month:
        year, m = map(int, norm_month.split('-'))
        qs = qs.filter(date__year=year, date__month=m)

    if category:
        clean_cat = category.strip().lower()
        qs = qs.filter(category__name__icontains=clean_cat) | qs.filter(category__type__icontains=clean_cat)

    total_matching = qs.count()
    records = qs.order_by('-date', '-id')[:limit]

    results = [
        {
            'transaction_id': f"Tx #{tx.id}",
            'id': tx.id,
            'date': str(tx.date),
            'description': tx.description,
            'amount': f"${tx.amount:,.2f}",
            'category': tx.category.name if tx.category else 'Uncategorized',
            'status': tx.status,
            'source_row': tx.source_row
        }
        for tx in records
    ]

    return {
        'filter_category': category,
        'filter_month': norm_month,
        'total_matching_count': total_matching,
        'returned_count': len(results),
        'transactions': results
    }


def get_review_items() -> Dict[str, Any]:
    """
    Returns items currently pending controller review in the review queue.
    Includes transaction IDs, anomalies flagged, amounts, and reason details.
    """
    items = detect_review_items(include_resolved=False)
    serialized = []

    for item in items:
        tx = item['transaction']
        reasons_list = [r['badge'] for r in item['reasons']]
        details_list = [r['detail'] for r in item['reasons']]
        serialized.append({
            'transaction_id': f"Tx #{tx.id}",
            'id': tx.id,
            'date': str(tx.date),
            'description': tx.description,
            'amount': f"${tx.amount:,.2f}",
            'category': tx.category.name if tx.category else 'Uncategorized',
            'confidence': tx.confidence,
            'reasons': reasons_list,
            'details': details_list,
            'review_url': f"/needs-review/?status=pending"
        })

    return {
        'pending_review_count': len(serialized),
        'items': serialized
    }


def get_variances() -> Dict[str, Any]:
    """
    Returns detected material month-over-month variances with driver categories
    and top driver transactions including transaction IDs.
    """
    variances = find_material_variances()
    serialized = []

    for v in variances:
        top_txs = [
            f"Tx (date: {t['date']}, desc: '{t['description']}', amt: ${t['amount']:,.2f}, cat: {t['category']})"
            for t in v['top_transactions']
        ]
        serialized.append({
            'line': v['line_label'],
            'period': f"{v['from_month_label']} -> {v['to_month_label']}",
            'dollar_change': f"${v['dollar_change']:+,.2f}",
            'percentage_change': f"{v['pct_change']}%",
            'direction': v['direction'],
            'prior_amount': f"${v['prior_amount']:,.2f}",
            'current_amount': f"${v['current_amount']:,.2f}",
            'driver_categories': [
                f"{c['category']} (change: ${c['dollar_change']:+,.2f})"
                for c in v['driver_categories']
            ],
            'top_transactions': top_txs,
            'view_transactions_url': v['view_transactions_url']
        })

    return {
        'total_material_variances': len(serialized),
        'variances': serialized
    }
