import re
from decimal import Decimal
from typing import Any, Set, List, Tuple


def extract_numbers_from_text(text: str) -> Set[str]:
    """
    Extracts all monetary amounts, percentages, and financial numbers from text.
    Normalizes them to comparable strings (e.g. '$150,535.07' -> '150535.07').
    Ignores common non-financial integers like calendar years (2026) and list counters (1-10).
    """
    # Match currency ($123.45, $-500, $+1,000), percentages (10.9%), and decimals (124.2)
    # Using raw regex avoiding regex escape collisions
    pattern = r'(?:[\$\+\-]?\d+(?:,\d{3})*(?:\.\d+)?%?|\b\d+\.\d+\b)'
    raw_tokens = re.findall(pattern, text)

    extracted = set()
    # Safe non-financial numbers to ignore
    ignore_set = {'2026', '2025', '2024', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10'}

    for token in raw_tokens:
        clean = token.replace('$', '').replace('%', '').replace(',', '').lstrip('+-').strip()
        if not clean:
            continue
        if clean in ignore_set:
            continue
        try:
            # Normalize to 2 decimal places if float/decimal, or clean int
            if '.' in clean:
                val = f"{float(clean):.2f}"
                extracted.add(val)
                # Also add 1-decimal form for percentages like 10.9
                extracted.add(f"{float(clean):.1f}")
            else:
                extracted.add(clean)
        except ValueError:
            continue

    return extracted


def extract_numbers_from_tool_data(data: Any) -> Set[str]:
    """
    Recursively extracts all numeric values from structured tool output.
    Normalizes floats, Decimals, integers, and currency strings.
    """
    found = set()

    if isinstance(data, dict):
        for k, v in data.items():
            found.update(extract_numbers_from_tool_data(v))
    elif isinstance(data, (list, tuple, set)):
        for item in data:
            found.update(extract_numbers_from_tool_data(item))
    elif isinstance(data, (int, float, Decimal)):
        c = abs(float(data))
        found.add(f"{c:.2f}")
        found.add(f"{c:.1f}")
        found.add(str(int(c)))
    elif isinstance(data, str):
        # Look for amounts inside strings like "$150,535.07" or "10.9%" or "Tx #170"
        tokens = re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', data)
        for t in tokens:
            clean = t.replace(',', '').strip()
            try:
                if '.' in clean:
                    found.add(f"{float(clean):.2f}")
                    found.add(f"{float(clean):.1f}")
                else:
                    found.add(clean)
            except ValueError:
                pass

    return found


def verify_response_numbers(
    response_text: str,
    tool_results: List[Any]
) -> Tuple[bool, List[str]]:
    """
    Checks that each financial number in response_text appears in tool_results.
    Returns:
        (is_valid: bool, unverified_numbers: list)
    """
    text_numbers = extract_numbers_from_text(response_text)
    allowed_numbers = extract_numbers_from_tool_data(tool_results)

    unverified = []
    for num in text_numbers:
        if num not in allowed_numbers:
            unverified.append(num)

    return (len(unverified) == 0, unverified)
