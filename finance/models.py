from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Category(models.Model):
    """Financial category for classifying transactions."""

    class CategoryType(models.TextChoices):
        REVENUE = 'revenue', 'Revenue'
        COGS = 'cogs', 'COGS'
        PAYROLL = 'payroll', 'Payroll'
        OPEX = 'opex', 'Opex'
        NON_PNL = 'non_pnl', 'Non-P&L'

    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=20, choices=CategoryType.choices)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"


class Transaction(models.Model):
    """Raw financial transaction record."""

    class Status(models.TextChoices):
        AUTO = 'auto', 'Auto'
        NEEDS_REVIEW = 'needs_review', 'Needs Review'
        CORRECTED = 'corrected', 'Corrected'
        RESOLVED = 'resolved', 'Resolved'

    date = models.DateField()
    description = models.CharField(max_length=255)
    # Stored as Decimal to ensure exact monetary precision (never float)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    # AI confidence score ranging from 0.0 to 1.0
    confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEEDS_REVIEW
    )
    # Determines whether this transaction flows into the P&L statement
    in_pnl = models.BooleanField(default=True)
    # Tracks the source line number from the uploaded file
    source_row = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.date} | {self.description} | {self.amount}"


class Correction(models.Model):
    """Audit log of category changes for human feedback / learning."""

    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name='corrections'
    )
    old_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='old_corrections'
    )
    new_category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='new_corrections'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        old = self.old_category.name if self.old_category else 'Uncategorized'
        return f"Tx {self.transaction_id}: {old} -> {self.new_category.name}"
