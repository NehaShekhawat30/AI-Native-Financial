import os
from django.core.management.base import BaseCommand, CommandError
from finance.services.importer import import_transactions_from_path


class Command(BaseCommand):
    help = 'Imports transactions from a CSV file into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
            type=str,
            help='Path to the transactions CSV file'
        )

    def handle(self, *args, **options):
        file_path = options['file_path']
        if not os.path.exists(file_path):
            raise CommandError(f"File not found: '{file_path}'")

        self.stdout.write(f"Importing transactions from '{file_path}'...")
        summary = import_transactions_from_path(file_path)

        self.stdout.write("=" * 50)
        self.stdout.write(self.style.SUCCESS(f"Rows Read:    {summary['rows_read']}"))
        self.stdout.write(self.style.SUCCESS(f"Rows Saved:   {summary['rows_saved']}"))
        self.stdout.write(
            self.style.WARNING(f"Rows Skipped: {summary['rows_skipped']}")
            if summary['rows_skipped'] > 0
            else f"Rows Skipped: {summary['rows_skipped']}"
        )
        self.stdout.write("=" * 50)

        if summary['skipped_details']:
            self.stdout.write(self.style.WARNING("Skipped Row Details:"))
            for detail in summary['skipped_details']:
                self.stdout.write(f"  - Row {detail['row']}: {detail['reason']}")
