import io
import json
from decimal import Decimal
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from finance.models import Transaction, Category, Correction
from finance.services.importer import import_transactions_from_stream
from finance.services.pnl import calculate_monthly_pnl
from finance.services.variances import (
    get_variances_with_explanations,
    PERCENT_THRESHOLD,
    ABSOLUTE_THRESHOLD,
)
from finance.services.review_detector import detect_review_items
from finance.services.chat_analyst import process_chat_message


@require_http_methods(["GET", "POST"])
def upload_transactions_view(request):
    """View to handle CSV transaction file upload and show import summary."""
    context = {}

    if request.method == "POST":
        uploaded_file = request.FILES.get('csv_file')
        if not uploaded_file:
            context['error_message'] = "Please select a CSV file to upload."
            return render(request, 'finance/upload.html', context)

        if not uploaded_file.name.endswith('.csv'):
            context['error_message'] = "Invalid file type. Please upload a .csv file."
            return render(request, 'finance/upload.html', context)

        try:
            # Read decoded text stream from uploaded file
            decoded_file = io.StringIO(uploaded_file.read().decode('utf-8-sig'))
            summary = import_transactions_from_stream(decoded_file, filename=uploaded_file.name)
            context['summary'] = summary
        except Exception as e:
            context['error_message'] = f"Failed to parse file: {str(e)}"

    return render(request, 'finance/upload.html', context)


def transaction_list_view(request):
    """
    Displays transactions with filters (category, category type, month, needs review, in_pnl)
    and highlights rows requiring manual review.
    Calculates totals strictly via SQL/Python Decimal (Rule 1 & Rule 4).
    """
    qs = Transaction.objects.select_related('category').all().order_by('-date', '-id')

    # Filter: Category ID
    selected_category = request.GET.get('category', '').strip()
    if selected_category and selected_category.isdigit():
        qs = qs.filter(category_id=int(selected_category))

    # Filter: Category Type (e.g. 'revenue', 'cogs', or 'revenue,cogs' for drilldowns)
    selected_type = request.GET.get('type', '').strip()
    if selected_type:
        type_list = [t.strip().lower() for t in selected_type.split(',') if t.strip()]
        qs = qs.filter(category__type__in=type_list)

    # Filter: In P&L only (e.g. 'true' or 'false')
    selected_in_pnl = request.GET.get('in_pnl', '').strip().lower()
    if selected_in_pnl in ('true', '1'):
        qs = qs.filter(in_pnl=True)
    elif selected_in_pnl in ('false', '0'):
        qs = qs.filter(in_pnl=False)

    # Filter: Month (e.g. '2026-01')
    selected_month = request.GET.get('month', '').strip()
    if selected_month and len(selected_month) == 7:
        try:
            year, month = map(int, selected_month.split('-'))
            qs = qs.filter(date__year=year, date__month=month)
        except ValueError:
            pass

    # Filter: Needs Review Only
    needs_review_only = request.GET.get('needs_review') in ('true', '1', 'on')
    if needs_review_only:
        qs = qs.filter(status=Transaction.Status.NEEDS_REVIEW)

    # Filter: Search query in description
    search_query = request.GET.get('q', '').strip()
    if search_query:
        qs = qs.filter(description__icontains=search_query)

    # Financial totals calculated strictly via SQL (Rule 1 & Rule 4)
    total_amount = qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_count = qs.count()
    global_needs_review_count = Transaction.objects.filter(
        status=Transaction.Status.NEEDS_REVIEW
    ).count()

    # Pagination: 50 items per page
    paginator = Paginator(qs, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Context options
    categories = Category.objects.all().order_by('type', 'name')
    months = Transaction.objects.dates('date', 'month', order='ASC')

    context = {
        'page_obj': page_obj,
        'categories': categories,
        'months': [m.strftime('%Y-%m') for m in months],
        'total_amount': total_amount,
        'total_count': total_count,
        'global_needs_review_count': global_needs_review_count,
        'selected_category': selected_category,
        'selected_type': selected_type,
        'selected_in_pnl': selected_in_pnl,
        'selected_month': selected_month,
        'needs_review_only': needs_review_only,
        'search_query': search_query,
    }
    return render(request, 'finance/transactions.html', context)


def pnl_view(request):
    """
    Renders the monthly Profit & Loss statement computed strictly by Python/SQL.
    Each number is an interactive drill-down link to backing transactions.
    """
    pnl_data = calculate_monthly_pnl()
    return render(request, 'finance/pnl.html', {'pnl': pnl_data})


def variances_view(request):
    """
    Finds material variances between consecutive months using plain code only,
    and provides concise LLM qualitative explanations.
    """
    variances = get_variances_with_explanations()
    context = {
        'variances': variances,
        'percent_threshold': PERCENT_THRESHOLD,
        'absolute_threshold': ABSOLUTE_THRESHOLD,
    }
    return render(request, 'finance/variances.html', context)


def needs_review_view(request):
    """
    Lists anomalies detected via rule-based code:
    - low-confidence categories
    - unusual amounts (far above typical size)
    - possible duplicates
    - non-P&L items needing special accounting treatment
    - missing or odd data
    """
    status_filter = request.GET.get('status', 'pending') # 'pending' or 'all'
    reason_filter = request.GET.get('reason', '').strip()

    include_resolved = (status_filter == 'all')
    all_detected = detect_review_items(include_resolved=True)

    # Filter items
    filtered_items = []
    pending_count = 0
    resolved_count = 0

    for item in all_detected:
        if item['is_resolved']:
            resolved_count += 1
        else:
            pending_count += 1

        # Check status filter
        if status_filter == 'pending' and item['is_resolved']:
            continue

        # Check reason filter
        if reason_filter:
            types = [r['type'] for r in item['reasons']]
            if reason_filter not in types:
                continue

        filtered_items.append(item)

    categories = Category.objects.all().order_by('type', 'name')

    context = {
        'items': filtered_items,
        'categories': categories,
        'status_filter': status_filter,
        'reason_filter': reason_filter,
        'pending_count': pending_count,
        'resolved_count': resolved_count,
        'total_count': len(all_detected),
    }
    return render(request, 'finance/needs_review.html', context)


@require_http_methods(["POST"])
def resolve_transaction(request, pk):
    """
    Marks a transaction as resolved.
    """
    tx = get_object_or_404(Transaction, pk=pk)
    tx.status = Transaction.Status.RESOLVED
    tx.save()
    return JsonResponse({
        'success': True,
        'transaction_id': tx.id,
        'status': tx.status
    })


def chat_view(request):
    """
    Renders the AI Financial Analyst conversational assistant page.
    Loads session history.
    """
    history = request.session.get('chat_history', [])
    return render(request, 'finance/chat.html', {'history': history})


@require_http_methods(["POST"])
def chat_api(request):
    """
    Processes chat requests via LLM tool calling.
    Answers strictly from tool results and logs backing transaction IDs.
    Preserves session conversation history.
    """
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    if not user_message:
        return JsonResponse({'success': False, 'error': 'Message cannot be empty'}, status=400)

    # Retrieve session history
    history = request.session.get('chat_history', [])

    # Process message with tool calling
    response_text, tools_called = process_chat_message(user_message, history)

    # Update session history
    history.append({'role': 'user', 'content': user_message})
    history.append({
        'role': 'assistant',
        'content': response_text,
        'tools_called': tools_called
    })
    request.session['chat_history'] = history
    request.session.modified = True

    return JsonResponse({
        'success': True,
        'response': response_text,
        'tools_called': tools_called,
        'history': history
    })


@require_http_methods(["POST"])
def clear_chat_api(request):
    """
    Clears the conversational chat session history.
    """
    request.session['chat_history'] = []
    request.session.modified = True
    return JsonResponse({'success': True})


@require_http_methods(["POST"])
def correct_transaction_category(request, pk):
    """
    Updates a transaction's category.
    Sets status = 'corrected', sets in_pnl according to new category,
    writes a Correction audit record, and optionally applies to matching descriptions.
    """
    tx = get_object_or_404(Transaction, pk=pk)

    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        category_id = data.get('category_id')
        apply_to_all = data.get('apply_to_all_matching', False)
    else:
        category_id = request.POST.get('category_id')
        apply_to_all = request.POST.get('apply_to_all_matching') in ('true', '1', 'on')

    if not category_id:
        return JsonResponse({'success': False, 'error': 'Category ID is required'}, status=400)

    new_cat = get_object_or_404(Category, pk=category_id)
    old_cat = tx.category

    # Update primary transaction
    tx.category = new_cat
    tx.status = Transaction.Status.CORRECTED
    tx.in_pnl = (new_cat.type != Category.CategoryType.NON_PNL)
    tx.save()

    # Create audit record
    Correction.objects.create(
        transaction=tx,
        old_category=old_cat,
        new_category=new_cat
    )

    updated_count = 1

    # Optional: Apply to other transactions with the exact same description
    if apply_to_all:
        matching_txs = Transaction.objects.filter(
            description=tx.description
        ).exclude(pk=tx.pk)

        for other in matching_txs:
            prev_cat = other.category
            other.category = new_cat
            other.status = Transaction.Status.CORRECTED
            other.in_pnl = (new_cat.type != Category.CategoryType.NON_PNL)
            other.save()

            Correction.objects.create(
                transaction=other,
                old_category=prev_cat,
                new_category=new_cat
            )
            updated_count += 1

    return JsonResponse({
        'success': True,
        'updated_count': updated_count,
        'transaction_id': tx.id,
        'new_category_id': new_cat.id,
        'new_category_name': new_cat.name,
        'new_category_type': new_cat.get_type_display(),
        'in_pnl': tx.in_pnl,
        'status': tx.status,
    })


def get_matching_count(request, pk):
    """Returns how many other transactions share the same description."""
    tx = get_object_or_404(Transaction, pk=pk)
    count = Transaction.objects.filter(description=tx.description).exclude(pk=tx.pk).count()
    return JsonResponse({
        'description': tx.description,
        'matching_count': count
    })
