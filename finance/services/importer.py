import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.db import transaction
from finance.models import Transaction


def clean_amount(raw_amount: str) -> Decimal:
    """
    Cleans a currency string into a Python Decimal.
    Handles: '-$9,000.00', '$-875.00', '($500.00)', '$17,513.84', etc.
    Never uses float (Rule 4).
    """
    cleaned = raw_amount.strip().replace('"', '').replace("'", "")
    
    # Check for negative in parentheses: ($500.00)
    is_negative = False
    if cleaned.startswith('(') and cleaned.endswith(')'):
        is_negative = True
        cleaned = cleaned[1:-1].strip()
    
    # Check for leading/trailing minus signs
    if '-' in cleaned:
        is_negative = True
        cleaned = cleaned.replace('-', '')
        
    # Remove currency symbol and comma separators
    cleaned = cleaned.replace('$', '').replace(',', '').strip()
    
    if not cleaned:
        raise ValueError("Empty amount string")
        
    amount = Decimal(cleaned)
    if is_negative:
        amount = -amount
        
    return amount.quantize(Decimal('0.01'))


def clean_date(raw_date: str):
    """
    Parses date strings into a datetime.date object.
    Supports ISO format (YYYY-MM-DD) and common variants.
    """
    cleaned = raw_date.strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: '{raw_date}'")


def import_transactions_from_stream(stream, filename: str = 'uploaded_file.csv') -> dict:
    """
    Reads a CSV stream, cleans dates and amounts, skips duplicates,
    and saves each valid row as a Transaction record with source_row.
    """
    reader = csv.reader(stream)
    
    # Read header row
    try:
        header = next(reader)
    except StopIteration:
        return {
            'rows_read': 0,
            'rows_saved': 0,
            'rows_skipped': 0,
            'skipped_details': [{'row': 1, 'reason': 'File is empty'}]
        }

    # Normalize header column positions
    col_map = {}
    for idx, col in enumerate(header):
        normalized = col.strip().lower().replace('_', ' ')
        col_map[normalized] = idx

    # Determine indices for required columns
    date_col = col_map.get('date', 1)
    desc_col = col_map.get('description', 2)
    counterparty_col = col_map.get('counterparty')
    amount_col = col_map.get('amount', 4)

    rows_read = 0
    rows_saved = 0
    rows_skipped = 0
    skipped_details = []
    seen_in_batch = set()

    for row_idx, row in enumerate(reader, start=2):
        rows_read += 1

        # Check for completely blank rows
        if not row or all(cell.strip() == '' for cell in row):
            rows_skipped += 1
            skipped_details.append({'row': row_idx, 'reason': 'Blank row'})
            continue

        # Extract values
        try:
            date_raw = row[date_col] if len(row) > date_col else ''
            desc_raw = row[desc_col] if len(row) > desc_col else ''
            amt_raw = row[amount_col] if len(row) > amount_col else ''
            
            # Optionally include counterparty in description if present
            counterparty = row[counterparty_col].strip() if counterparty_col and len(row) > counterparty_col else ''
            description = desc_raw.strip()
            if counterparty and counterparty.lower() not in description.lower():
                description = f"{description} - {counterparty}"
        except IndexError:
            rows_skipped += 1
            skipped_details.append({'row': row_idx, 'reason': 'Missing columns'})
            continue

        # Parse date
        try:
            tx_date = clean_date(date_raw)
        except ValueError as e:
            rows_skipped += 1
            skipped_details.append({'row': row_idx, 'reason': f"Invalid date: {str(e)}"})
            continue

        # Parse amount (Decimal, never float)
        try:
            tx_amount = clean_amount(amt_raw)
        except (ValueError, InvalidOperation) as e:
            rows_skipped += 1
            skipped_details.append({'row': row_idx, 'reason': f"Invalid amount: {amt_raw}"})
            continue

        # Check for exact duplicate within current batch
        dupe_key = (tx_date, description, tx_amount)
        if dupe_key in seen_in_batch:
            rows_skipped += 1
            skipped_details.append({'row': row_idx, 'reason': 'Duplicate row in uploaded file'})
            continue

        # Check for exact duplicate in database
        if Transaction.objects.filter(date=tx_date, description=description, amount=tx_amount).exists():
            rows_skipped += 1
            skipped_details.append({'row': row_idx, 'reason': 'Duplicate transaction already in database'})
            continue

        # Save valid transaction
        Transaction.objects.create(
            date=tx_date,
            description=description,
            amount=tx_amount,
            source_row=row_idx,
            status=Transaction.Status.NEEDS_REVIEW,
            in_pnl=True
        )
        seen_in_batch.add(dupe_key)
        rows_saved += 1

    return {
        'rows_read': rows_read,
        'rows_saved': rows_saved,
        'rows_skipped': rows_skipped,
        'skipped_details': skipped_details
    }


def import_transactions_from_path(file_path: str) -> dict:
    """Reads a CSV file from a disk path and imports transactions."""
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        return import_transactions_from_stream(f, filename=file_path)
