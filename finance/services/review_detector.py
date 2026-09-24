from decimal import Decimal
from typing import List, Dict, Any
from collections import defaultdict
from finance.models import Transaction, Category


def detect_review_items(include_resolved: bool = False) -> List[Dict[str, Any]]:
    """
    Detects transactions requiring controller review using deterministic rule-based code.
    Rule 1 & Rule 2: NO LLM used for detection.

    Detection Rules:
    1. Low-confidence categories (confidence < 0.70 or status == 'needs_review')
    2. Unusual amounts (amount > 1.5x of the category's typical average and diff >= $1,000)
    3. Possible duplicates (same date, amount, and description)
    4. Non-P&L items (capital expenditures, debt repayment, taxes, owner distributions)
    5. Missing or odd data (uncategorized, blank description, zero amount, etc.)
    """
    qs = Transaction.objects.select_related('category').all().order_by('-date', '-id')
    if not include_resolved:
        qs = qs.exclude(status=Transaction.Status.RESOLVED)

    transactions = list(qs)
    all_tx_in_db = list(Transaction.objects.select_related('category').all())

    # Pre-compute category averages (separating deposits from expenses to avoid distortion)
    cat_expenses = defaultdict(list)
    cat_deposits = defaultdict(list)
    for tx in all_tx_in_db:
        if tx.category:
            if tx.amount < 0:
                cat_expenses[tx.category.name].append(abs(tx.amount))
            elif tx.amount > 0:
                cat_deposits[tx.category.name].append(tx.amount)

    cat_expense_avg = {
        name: (sum(amts) / len(amts))
        for name, amts in cat_expenses.items()
        if len(amts) >= 2
    }
    cat_deposit_avg = {
        name: (sum(amts) / len(amts))
        for name, amts in cat_deposits.items()
        if len(amts) >= 2
    }

    # Pre-compute duplicates by (date, amount, description)
    seen_signatures = defaultdict(list)
    for tx in all_tx_in_db:
        sig = (tx.date, tx.amount, tx.description.strip().lower())
        seen_signatures[sig].append(tx.id)

    review_items = []
    seen_tx_ids = set()

    for tx in transactions:
        reasons = []

        # ----------------------------------------------------
        # Rule 1: Low Confidence (< 0.70)
        # ----------------------------------------------------
        if tx.confidence is not None and tx.confidence < 0.70:
            reasons.append({
                'type': 'low_confidence',
                'badge': f"Low Confidence ({tx.confidence:.2f})",
                'severity': 'warning',
                'detail': f"Categorization confidence {tx.confidence:.2f} is below the 0.70 certainty threshold."
            })
        elif tx.status == Transaction.Status.NEEDS_REVIEW and tx.confidence is None:
            reasons.append({
                'type': 'low_confidence',
                'badge': "Unverified Status",
                'severity': 'warning',
                'detail': "Transaction flagged for manual verification."
            })

        # ----------------------------------------------------
        # Rule 2: Unusual Amounts (Far above category's typical size)
        # ----------------------------------------------------
        if tx.category:
            curr_val = abs(tx.amount)
            if tx.amount < 0 and tx.category.name in cat_expense_avg:
                avg = cat_expense_avg[tx.category.name]
                if curr_val >= avg * Decimal('1.5') and (curr_val - avg) >= Decimal('1000.00'):
                    ratio = float(round(curr_val / avg, 1))
                    reasons.append({
                        'type': 'unusual_amount',
                        'badge': f"Unusual Size ({ratio}x Avg)",
                        'severity': 'danger',
                        'detail': f"Amount ${curr_val:,.2f} is {ratio}x higher than typical {tx.category.name} average (${avg:,.2f})."
                    })
            elif tx.amount > 0 and tx.category.name in cat_deposit_avg:
                avg = cat_deposit_avg[tx.category.name]
                if curr_val >= avg * Decimal('1.5') and (curr_val - avg) >= Decimal('1000.00'):
                    ratio = float(round(curr_val / avg, 1))
                    reasons.append({
                        'type': 'unusual_amount',
                        'badge': f"Unusual Size ({ratio}x Avg)",
                        'severity': 'danger',
                        'detail': f"Amount ${curr_val:,.2f} is {ratio}x higher than typical {tx.category.name} average (${avg:,.2f})."
                    })

        # ----------------------------------------------------
        # Rule 3: Possible Duplicates
        # ----------------------------------------------------
        sig = (tx.date, tx.amount, tx.description.strip().lower())
        duplicate_ids = seen_signatures.get(sig, [])
        if len(duplicate_ids) > 1:
            other_ids = [str(_id) for _id in duplicate_ids if _id != tx.id]
            reasons.append({
                'type': 'possible_duplicate',
                'badge': "Possible Duplicate",
                'severity': 'danger',
                'detail': f"Identical date, amount, and description matches transaction(s) #{', #'.join(other_ids)}."
            })

        # ----------------------------------------------------
        # Rule 4: Non-P&L Items Needing Special Accounting Review
        # ----------------------------------------------------
        if tx.category and tx.category.type == Category.CategoryType.NON_PNL:
            reasons.append({
                'type': 'non_pnl',
                'badge': f"Non-P&L ({tx.category.name})",
                'severity': 'info',
                'detail': f"Excluded from P&L as {tx.category.name}. Verify if this should be capitalized, depreciated, or expensed."
            })

        # ----------------------------------------------------
        # Rule 5: Missing or Odd Data
        # ----------------------------------------------------
        odd_details = []
        if not tx.category:
            odd_details.append("Missing category assignment")
        if not tx.description or len(tx.description.strip()) == 0:
            odd_details.append("Missing description")
        if tx.amount == Decimal('0.00'):
            odd_details.append("Zero dollar amount")

        if odd_details:
            reasons.append({
                'type': 'odd_data',
                'badge': "Data Anomaly",
                'severity': 'danger',
                'detail': "; ".join(odd_details)
            })

        # If any rule matched, add to review list
        if reasons:
            primary_reason = reasons[0]
            review_items.append({
                'transaction': tx,
                'reasons': reasons,
                'primary_badge': primary_reason['badge'],
                'primary_severity': primary_reason['severity'],
                'primary_type': primary_reason['type'],
                'is_resolved': (tx.status == Transaction.Status.RESOLVED),
            })
            seen_tx_ids.add(tx.id)

    return review_items
