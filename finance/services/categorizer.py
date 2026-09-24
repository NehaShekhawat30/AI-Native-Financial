from typing import Dict, Any, List
from django.db import transaction
from finance.models import Transaction, Category
from finance.rules import match_keyword_rule
from finance.services.llm_client import call_llm_categorize_batch


def run_categorization(batch_size: int = 25, force_all: bool = False) -> Dict[str, Any]:
    """
    Executes 2-pass categorization:
    - Pass 1: Simple keyword rules (confidence = 1.0, status = auto)
    - Pass 2: LLM batch categorization for unmatched transactions
    Enforces strict category validation, confidence thresholds, and in_pnl flags.
    """
    # Fetch all allowed categories from database
    category_map = {c.name.strip().lower(): c for c in Category.objects.all()}
    allowed_names = [c.name for c in Category.objects.all()]

    # Select transactions to categorize
    query = Transaction.objects.all()
    if not force_all:
        query = query.filter(category__isnull=True)

    transactions_to_process = list(query)
    
    pass1_count = 0
    pass2_count = 0
    needs_review_count = 0
    rejected_count = 0
    unmatched_for_llm: List[Transaction] = []

    # ----------------------------------------------------
    # PASS 1: Simple Keyword Rules
    # ----------------------------------------------------
    for tx in transactions_to_process:
        matched_cat_name = match_keyword_rule(tx.description)
        if matched_cat_name:
            matched_key = matched_cat_name.strip().lower()
            category = category_map.get(matched_key)
            if category:
                tx.category = category
                tx.confidence = 1.0
                tx.status = Transaction.Status.AUTO
                # Set in_pnl = false for non_pnl categories
                tx.in_pnl = (category.type != Category.CategoryType.NON_PNL)
                tx.save()
                pass1_count += 1
                continue
        
        # If no rule matched, queue for Pass 2
        unmatched_for_llm.append(tx)

    # ----------------------------------------------------
    # PASS 2: Batch LLM Categorization
    # ----------------------------------------------------
    for i in range(0, len(unmatched_for_llm), batch_size):
        chunk = unmatched_for_llm[i:i + batch_size]
        payload = [
            {
                'id': tx.id,
                'date': str(tx.date),
                'description': tx.description,
                'amount': str(tx.amount)
            }
            for tx in chunk
        ]

        llm_results = call_llm_categorize_batch(payload, allowed_names)
        
        # Map responses by transaction id
        result_by_id = {r['id']: r for r in llm_results if isinstance(r, dict) and 'id' in r}

        for tx in chunk:
            res = result_by_id.get(tx.id)
            if not res:
                # LLM missed this item
                tx.status = Transaction.Status.NEEDS_REVIEW
                tx.confidence = 0.0
                tx.save()
                needs_review_count += 1
                continue

            proposed_cat = res.get('category', '').strip().lower()
            confidence_val = float(res.get('confidence', 0.0))

            # Validate against allowed categories list (reject if not found)
            if proposed_cat not in category_map:
                rejected_count += 1
                tx.status = Transaction.Status.NEEDS_REVIEW
                tx.confidence = 0.0
                tx.save()
                needs_review_count += 1
                continue

            category = category_map[proposed_cat]
            tx.category = category
            tx.confidence = round(confidence_val, 2)

            # Rule: Set status = needs_review when confidence < 0.7
            if tx.confidence < 0.7:
                tx.status = Transaction.Status.NEEDS_REVIEW
                needs_review_count += 1
            else:
                tx.status = Transaction.Status.AUTO

            # Rule: Set in_pnl = false for non_pnl categories
            tx.in_pnl = (category.type != Category.CategoryType.NON_PNL)
            tx.save()
            pass2_count += 1

    return {
        'total_evaluated': len(transactions_to_process),
        'pass1_rule_matched': pass1_count,
        'pass2_llm_categorized': pass2_count,
        'flagged_needs_review': needs_review_count,
        'rejected_invalid_categories': rejected_count,
    }
