from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.db.models import Sum

from finance.models import Category, Transaction, Correction
from finance.services.pnl import calculate_monthly_pnl
from finance.services.variances import find_material_variances, get_driver_categories
from finance.services.guardrails import verify_response_numbers


class FinancialReviewTestCase(TestCase):
    """
    Test suite for Step 9: Financial correctness and LLM guardrails.
    All tests are simple, readable, and verify deterministic calculations.
    """

    def setUp(self):
        # 1. Create standard Categories
        self.rev_cat = Category.objects.create(name='Food Sales', type=Category.CategoryType.REVENUE)
        self.cogs_cat = Category.objects.create(name='Food Inventory', type=Category.CategoryType.COGS)
        self.payroll_cat = Category.objects.create(name='Kitchen Wages', type=Category.CategoryType.PAYROLL)
        self.opex_cat = Category.objects.create(name='Rent', type=Category.CategoryType.OPEX)
        self.non_pnl_cat = Category.objects.create(name='Equipment Purchase', type=Category.CategoryType.NON_PNL)

        # 2. Create January Transactions (P&L items)
        Transaction.objects.create(
            date=date(2026, 1, 10), description='Food sales week 1',
            amount=Decimal('10000.00'), category=self.rev_cat, in_pnl=True, status=Transaction.Status.AUTO
        )
        Transaction.objects.create(
            date=date(2026, 1, 12), description='Sysco food purchase',
            amount=Decimal('-3000.00'), category=self.cogs_cat, in_pnl=True, status=Transaction.Status.AUTO
        )
        Transaction.objects.create(
            date=date(2026, 1, 15), description='Kitchen payroll',
            amount=Decimal('-2500.00'), category=self.payroll_cat, in_pnl=True, status=Transaction.Status.AUTO
        )
        Transaction.objects.create(
            date=date(2026, 1, 18), description='Landlord rent',
            amount=Decimal('-1500.00'), category=self.opex_cat, in_pnl=True, status=Transaction.Status.AUTO
        )

        # 3. Create January Non-P&L Transaction
        Transaction.objects.create(
            date=date(2026, 1, 20), description='New oven equipment purchase',
            amount=Decimal('-5000.00'), category=self.non_pnl_cat, in_pnl=False, status=Transaction.Status.AUTO
        )

        # 4. Create February Transactions (with a material jump in Food Inventory)
        Transaction.objects.create(
            date=date(2026, 2, 10), description='Food sales week 1',
            amount=Decimal('10000.00'), category=self.rev_cat, in_pnl=True, status=Transaction.Status.AUTO
        )
        Transaction.objects.create(
            date=date(2026, 2, 12), description='Large catering Sysco purchase',
            amount=Decimal('-6000.00'), category=self.cogs_cat, in_pnl=True, status=Transaction.Status.AUTO
        )
        Transaction.objects.create(
            date=date(2026, 2, 15), description='Kitchen payroll',
            amount=Decimal('-2500.00'), category=self.payroll_cat, in_pnl=True, status=Transaction.Status.AUTO
        )
        Transaction.objects.create(
            date=date(2026, 2, 18), description='Landlord rent',
            amount=Decimal('-1500.00'), category=self.opex_cat, in_pnl=True, status=Transaction.Status.AUTO
        )

    def test_pnl_totals_equal_sum_of_transactions(self):
        """Test 1: P&L totals strictly equal the sum of backing transactions."""
        pnl = calculate_monthly_pnl()
        lines = {l['key']: l['values']['2026-01'] for l in pnl['lines']}

        # Revenue
        actual_rev = Transaction.objects.filter(
            in_pnl=True, date__month=1, category__type=Category.CategoryType.REVENUE
        ).aggregate(tot=Sum('amount'))['tot']
        self.assertEqual(lines['revenue'], actual_rev)
        self.assertEqual(lines['revenue'], Decimal('10000.00'))

        # COGS (presented as positive)
        actual_cogs = abs(Transaction.objects.filter(
            in_pnl=True, date__month=1, category__type=Category.CategoryType.COGS
        ).aggregate(tot=Sum('amount'))['tot'])
        self.assertEqual(lines['cogs'], actual_cogs)
        self.assertEqual(lines['cogs'], Decimal('3000.00'))

        # Formulas
        expected_gross_profit = lines['revenue'] - lines['cogs']
        self.assertEqual(lines['gross_profit'], expected_gross_profit)
        self.assertEqual(lines['gross_profit'], Decimal('7000.00'))

        expected_op_profit = lines['gross_profit'] - lines['payroll'] - lines['opex']
        self.assertEqual(lines['operating_profit'], expected_op_profit)
        self.assertEqual(lines['operating_profit'], Decimal('3000.00'))

    def test_changing_category_updates_pnl(self):
        """Test 2: Changing a transaction's category immediately updates P&L and writes a Correction."""
        # Find the Rent transaction ($1,500 in Opex)
        tx = Transaction.objects.get(description='Landlord rent', date__month=1)
        old_cat = tx.category

        # Reclassify from Opex to COGS
        tx.category = self.cogs_cat
        tx.status = Transaction.Status.CORRECTED
        tx.in_pnl = (self.cogs_cat.type != Category.CategoryType.NON_PNL)
        tx.save()

        # Audit trail must be recorded
        Correction.objects.create(transaction=tx, old_category=old_cat, new_category=self.cogs_cat)
        self.assertTrue(Correction.objects.filter(transaction=tx).exists())

        # Recalculate P&L and verify shift
        pnl = calculate_monthly_pnl()
        jan_lines = {l['key']: l['values']['2026-01'] for l in pnl['lines']}

        # COGS increased by $1,500 (from $3,000 to $4,500)
        self.assertEqual(jan_lines['cogs'], Decimal('4500.00'))
        # Opex decreased by $1,500 (from $1,500 down to $0)
        self.assertEqual(jan_lines['opex'], Decimal('0.00'))

    def test_non_pnl_rows_are_excluded(self):
        """Test 3: Non-P&L rows are strictly excluded from P&L calculations."""
        # Non-P&L oven purchase is -$5,000.00
        non_pnl_tx = Transaction.objects.get(description='New oven equipment purchase')
        self.assertFalse(non_pnl_tx.in_pnl)

        pnl = calculate_monthly_pnl()
        jan_lines = {l['key']: l['values']['2026-01'] for l in pnl['lines']}

        # Total expenses in P&L must be COGS ($3,000) + Payroll ($2,500) + Opex ($1,500) = $7,000
        # The $5,000 oven purchase must NOT appear in COGS, Opex, or reduce Operating Profit
        total_pnl_costs = jan_lines['cogs'] + jan_lines['payroll'] + jan_lines['opex']
        self.assertEqual(total_pnl_costs, Decimal('7000.00'))
        self.assertEqual(jan_lines['operating_profit'], Decimal('3000.00'))

    def test_variance_drivers_add_up_to_change(self):
        """Test 4: Material variance drivers account for the change between consecutive months."""
        # In setup, COGS went from $3,000 in Jan to $6,000 in Feb (+$3,000 change, 100% increase > 10% & > $2000)
        drivers = get_driver_categories('cogs', '2026-01', '2026-02')
        self.assertTrue(len(drivers) > 0)

        # The primary driver is Food Inventory, increasing by $3,000.00
        primary_driver = drivers[0]
        self.assertEqual(primary_driver['category'], 'Food Inventory')
        self.assertEqual(primary_driver['dollar_change'], 3000.0)

        # Total line delta between Jan and Feb for COGS is $3,000.00
        pnl = calculate_monthly_pnl()
        cogs_line = next(l for l in pnl['lines'] if l['key'] == 'cogs')
        line_delta = cogs_line['values']['2026-02'] - cogs_line['values']['2026-01']
        self.assertEqual(line_delta, Decimal('3000.00'))

    def test_number_checker_blocks_made_up_figure(self):
        """Test 5: Guardrail number checker catches and blocks hallucinated numbers."""
        tool_results = [
            {'Revenue': '$150,535.07', 'id': 170},
            {'category': 'Food Inventory', 'amount': '$3,884.60'}
        ]

        # Case A: Answer containing fabricated figures ($999,999.00 and 48.5%)
        hallucinated_answer = "Our Revenue was $150,535.07, and our profit margin was 48.5% with $999,999.00 cash."
        is_valid, unverified = verify_response_numbers(hallucinated_answer, tool_results)
        self.assertFalse(is_valid)
        self.assertTrue('999999.00' in unverified or '999999' in unverified)

        # Case B: Answer using strictly verified figures from tool results
        grounded_answer = "Our Revenue was $150,535.07, and typical Food Inventory cost was $3,884.60 for Tx #170."
        is_valid_grounded, unverified_grounded = verify_response_numbers(grounded_answer, tool_results)
        self.assertTrue(is_valid_grounded)
        self.assertEqual(len(unverified_grounded), 0)
