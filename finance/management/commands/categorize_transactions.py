from django.core.management.base import BaseCommand
from finance.services.categorizer import run_categorization


class Command(BaseCommand):
    help = 'Categorizes transactions using Pass 1 (rules) and Pass 2 (LLM in batches)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-evaluate all transactions, including already categorized ones'
        )

    def handle(self, *args, **options):
        force = options['force']
        self.stdout.write("Running 2-pass categorization...")
        
        summary = run_categorization(force_all=force)

        self.stdout.write("=" * 55)
        self.stdout.write(f"Total Evaluated:              {summary['total_evaluated']}")
        self.stdout.write(self.style.SUCCESS(f"Pass 1 (Rules Matched):       {summary['pass1_rule_matched']}"))
        self.stdout.write(self.style.SUCCESS(f"Pass 2 (LLM Categorized):     {summary['pass2_llm_categorized']}"))
        self.stdout.write(
            self.style.WARNING(f"Flagged 'Needs Review' (<0.7): {summary['flagged_needs_review']}")
        )
        if summary['rejected_invalid_categories'] > 0:
            self.stdout.write(
                self.style.ERROR(f"Rejected (Invalid Category):  {summary['rejected_invalid_categories']}")
            )
        self.stdout.write("=" * 55)
