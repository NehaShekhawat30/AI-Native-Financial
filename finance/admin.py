from django.contrib import admin
from .models import Category, Transaction, Correction


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type')
    list_filter = ('type',)
    search_fields = ('name',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'description', 'amount', 'category', 'confidence', 'status', 'in_pnl')
    list_filter = ('status', 'in_pnl', 'category__type')
    search_fields = ('description',)


@admin.register(Correction)
class CorrectionAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'old_category', 'new_category', 'created_at')
    list_filter = ('created_at',)
