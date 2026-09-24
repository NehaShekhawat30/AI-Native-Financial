from django.core.management.base import BaseCommand
from finance.models import Category


class Command(BaseCommand):
    help = 'Seeds a sensible chart of accounts for financial categorization'

    def handle(self, *args, **options):
        # Sensible Chart of Accounts grouped by category type
        accounts = [
            # Revenue (P&L)
            ('Food Sales', Category.CategoryType.REVENUE),
            ('Beverage Sales', Category.CategoryType.REVENUE),
            ('Catering Revenue', Category.CategoryType.REVENUE),
            ('Delivery App Payouts', Category.CategoryType.REVENUE),
            ('Other Revenue', Category.CategoryType.REVENUE),

            # Cost of Goods Sold (P&L)
            ('Food Inventory', Category.CategoryType.COGS),
            ('Beverage Inventory', Category.CategoryType.COGS),
            ('Kitchen & Packaging Supplies', Category.CategoryType.COGS),

            # Payroll (P&L)
            ('Front of House Wages', Category.CategoryType.PAYROLL),
            ('Kitchen Wages', Category.CategoryType.PAYROLL),
            ('Salaries & Management', Category.CategoryType.PAYROLL),
            ('Payroll Taxes & Benefits', Category.CategoryType.PAYROLL),

            # Operating Expenses (P&L)
            ('Rent & Occupancy', Category.CategoryType.OPEX),
            ('Utilities', Category.CategoryType.OPEX),
            ('Software & POS Subscriptions', Category.CategoryType.OPEX),
            ('Insurance', Category.CategoryType.OPEX),
            ('Marketing & Advertising', Category.CategoryType.OPEX),
            ('Accounting & Legal', Category.CategoryType.OPEX),
            ('Repairs & Maintenance', Category.CategoryType.OPEX),
            ('Merchant Processing Fees', Category.CategoryType.OPEX),
            ('General Office Expenses', Category.CategoryType.OPEX),

            # Non-P&L Balance Sheet / Cash Movements
            ('Loan Repayment', Category.CategoryType.NON_PNL),
            ('Owner Withdrawal', Category.CategoryType.NON_PNL),
            ('Internal Transfer', Category.CategoryType.NON_PNL),
            ('Tax Payment', Category.CategoryType.NON_PNL),
            ('Equipment Purchase', Category.CategoryType.NON_PNL),
        ]

        created_count = 0
        for name, cat_type in accounts:
            category, created = Category.objects.get_or_create(
                name=name,
                defaults={'type': cat_type}
            )
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded categories. {created_count} created, "
                f"{len(accounts) - created_count} already existed."
            )
        )
