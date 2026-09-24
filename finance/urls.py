from django.urls import path
from .views import (
    upload_transactions_view,
    transaction_list_view,
    pnl_view,
    variances_view,
    needs_review_view,
    resolve_transaction,
    chat_view,
    chat_api,
    clear_chat_api,
    correct_transaction_category,
    get_matching_count,
)

app_name = 'finance'

urlpatterns = [
    path('', pnl_view, name='pnl_home'),
    path('pnl/', pnl_view, name='pnl'),
    path('variances/', variances_view, name='variances'),
    path('needs-review/', needs_review_view, name='needs_review'),
    path('chat/', chat_view, name='chat'),
    path('api/chat/', chat_api, name='chat_api'),
    path('api/chat/clear/', clear_chat_api, name='clear_chat_api'),
    path('transactions/', transaction_list_view, name='transactions'),
    path('transactions/<int:pk>/correct/', correct_transaction_category, name='correct_transaction'),
    path('transactions/<int:pk>/resolve/', resolve_transaction, name='resolve_transaction'),
    path('transactions/<int:pk>/matching-count/', get_matching_count, name='matching_count'),
    path('upload/', upload_transactions_view, name='upload_transactions'),
]
