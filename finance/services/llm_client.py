import json
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()


def call_llm_categorize_batch(
    transactions: List[Dict[str, Any]],
    allowed_categories: List[str]
) -> List[Dict[str, Any]]:
    """
    Calls the LLM to categorize a batch of transactions.
    Strictly enforces JSON response with schema:
    [
        {"id": <int>, "category": "<str>", "confidence": <float 0-1>, "reason": "<str>"}
    ]
    """
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    
    # Prompt detailing role, allowed categories, and required JSON schema
    prompt = f"""You are an expert financial controller and CPA.
Categorize each of the following bank transactions into EXACTLY ONE of the allowed categories.

ALLOWED CATEGORIES (choose ONLY from this list, verbatim):
{json.dumps(allowed_categories, indent=2)}

TRANSACTIONS TO CATEGORIZE:
{json.dumps(transactions, indent=2)}

INSTRUCTIONS:
1. Return a JSON array of objects.
2. Each object must have:
   - "id": integer (the transaction id)
   - "category": string (must EXACTLY match one of the allowed categories)
   - "confidence": float between 0.0 and 1.0 (e.g. 0.95 for high certainty, 0.60 for ambiguous items)
   - "reason": string (a short one-line explanation for your choice)
3. Return ONLY valid JSON, with no markdown fences, no surrounding commentary.
"""

    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.1,
                }
            )
            raw_text = response.text.strip()
            # Clean possible markdown formatting
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1]
                if raw_text.endswith("```"):
                    raw_text = raw_text.rsplit("\n", 1)[0]
            parsed = json.loads(raw_text.strip())
            return parsed
        except Exception as e:
            # Fall back to heuristic mock if LLM network call fails
            print(f"Warning: Gemini API call failed ({e}). Using heuristic fallback.")

    # Graceful offline heuristic when GEMINI_API_KEY is not configured yet
    return _offline_heuristic_fallback(transactions, allowed_categories)


def _offline_heuristic_fallback(
    transactions: List[Dict[str, Any]],
    allowed_categories: List[str]
) -> List[Dict[str, Any]]:
    """
    Predictable offline classifier used when API key is not yet set.
    Allows local development, testing, and CI without incurring API charges.
    """
    results = []
    allowed_set = set(allowed_categories)

    for tx in transactions:
        desc = tx.get('description', '').lower()
        amt = float(tx.get('amount', 0))

        if 'marketing' in desc or 'ads' in desc:
            cat = 'Marketing & Advertising'
            conf = 0.95
            reason = 'Digital marketing and local advertising expenses.'
        elif 'license' in desc or 'licensing' in desc:
            cat = 'General Office Expenses'
            conf = 0.75
            reason = 'Government regulatory permit and licensing renewal fee.'
        elif 'internet' in desc or 'phone' in desc:
            cat = 'Utilities'
            conf = 0.85
            reason = 'Telecom and internet operating utility.'
        elif 'supplies' in desc or 'amazon' in desc or 'staples' in desc:
            cat = 'General Office Expenses'
            conf = 0.80
            reason = 'Office supplies and consumable administrative expenses.'
        elif 'gift card' in desc:
            # Ambiguous: Gift card deposit is unearned revenue liability, confidence below 0.7 to trigger review
            cat = 'Other Revenue'
            conf = 0.60
            reason = 'Gift card deposit represents unearned revenue liability requiring human review.'
        else:
            cat = 'General Office Expenses'
            conf = 0.50
            reason = 'Unmatched transaction defaulted for human controller review.'

        # Ensure category is strictly in allowed categories
        if cat not in allowed_set:
            cat = allowed_categories[0] if allowed_categories else 'Uncategorized'
            conf = 0.30

        results.append({
            'id': tx['id'],
            'category': cat,
            'confidence': conf,
            'reason': reason
        })

    return results
