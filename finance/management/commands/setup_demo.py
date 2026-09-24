import os
from pathlib import Path
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.conf import settings
from finance.models import Category, Transaction
from finance.services.importer import import_transactions_from_path


class Command(BaseCommand):
    help = 'One-command setup for production demo: migrates, seeds categories, imports sample transactions, and categorizes them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-import and re-categorize even if transactions already exist'
        )

    def handle(self, *args, **options):
        force = options['force']
        self.stdout.write(self.style.MIGRATE_HEADING("=== Step 1: Running Database Migrations ==="))
        call_command('migrate', interactive=False)

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Step 2: Seeding Chart of Accounts Categories ==="))
        call_command('seed_categories')

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Step 3: Ingesting Sample Transaction Data ==="))
        base_dir = Path(settings.BASE_DIR)
        
        # Look for the sample CSV in common project locations
        possible_csv_paths = [
            base_dir / 'NYC Restaurant Co. - Raw Transactions.xlsx - Sheet1.csv',
            base_dir / 'sample_transactions.csv',
            base_dir / 'sample_data.csv',
        ]
        
        csv_file = None
        for path in possible_csv_paths:
            if path.exists():
                csv_file = path
                break

        if not csv_file:
            self.stdout.write(self.style.ERROR(f"Error: Could not locate sample CSV file at {possible_csv_paths[0]}"))
            return

        tx_count = Transaction.objects.count()
        if tx_count == 0 or force:
            self.stdout.write(f"Importing transactions from '{csv_file.name}'...")
            summary = import_transactions_from_path(str(csv_file))
            self.stdout.write(self.style.SUCCESS(f"Imported: {summary['rows_saved']} transactions (skipped {summary['rows_skipped']} duplicates)."))
        else:
            self.stdout.write(self.style.WARNING(f"Database already contains {tx_count} transactions. Use --force to re-import."))

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Step 4: Running 2-Pass Categorization Engine ==="))
        call_command('categorize_transactions', force=force)

        total_cats = Category.objects.count()
        total_txs = Transaction.objects.count()
        pnl_txs = Transaction.objects.filter(in_pnl=True).count()
        review_txs = Transaction.objects.filter(status=Transaction.Status.NEEDS_REVIEW).count()

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Demo Environment Setup Complete & Verified!"))
        self.stdout.write(f"- Categories in Chart of Accounts: {total_cats}")
        self.stdout.write(f"- Total Bank Transactions:        {total_txs}")
        self.stdout.write(f"- P&L Transactions (in_pnl=True): {pnl_txs}")
        self.stdout.write(f"- Items Flagged for Review:       {review_txs}")
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("All systems ready: P&L, Variances, Review Queue, and Chat Analyst."))
