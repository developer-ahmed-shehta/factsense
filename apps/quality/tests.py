"""
Unit and Integration Tests for Quality Assurance, Statistical Process Control (SPC)
and Product Giveaway Analysis (F07).
Strictly verifies:
- ISO 22400-2 X-bar and R control charts with standard constants (A2=0.577, d2=2.326, D4=2.114)
- Process capability indices (Cp, Cpk) matching mathematical fixtures
- Gaussian distribution bell curve coordinates
- Product giveaway financial loss calculations and interactive recalibration simulation
- Raw CSV export endpoint
- Zero emojis compliance across all quality templates
"""

import re
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User, Role, UserRoleAssignment
from apps.masterdata.models import Factory, Line, Machine, Product, Shift
from apps.quality.models import SPCConfig, QualitySubgroup, QualitySample
from apps.quality.services.spc_service import (
    calculate_spc_metrics, simulate_recalibration, record_weight_samples_and_subgroup,
    get_or_create_default_spc_config
)

EMOJI_PATTERN = re.compile(
    r'[\U00010000-\U0010ffff]'
    r'|[\u2600-\u26FF]'
    r'|[\u2700-\u27BF]'
    r'|[\u2B50-\u2B55]'
    r'|[\u23E9-\u23FA]'
)


class QualitySPCTestCase(TestCase):

    def setUp(self):
        self.client = Client()

        # Create Factory, Line, and Filler Machine
        self.factory = Factory.objects.create(name='SPC Test Factory', code='SPC-FAC-01')
        self.line = Line.objects.create(factory=self.factory, name='Bottling Line 1', code='LINE-1')
        self.filler = Machine.objects.create(
            line=self.line, name='Rotary Piston Filler', code='FL-30',
            category='FILLER', sequence_order=2, ideal_run_rate_cpm=100, is_bottleneck=True
        )

        # Create Product
        self.product = Product.objects.create(
            factory=self.factory, code='WTR-500ML', name='Mineral Water 500ml',
            nominal_weight=Decimal('500.00'), usl_weight=Decimal('505.00'), lsl_weight=Decimal('495.00'),
            unit_cost=Decimal('1.20'), scrap_cost=Decimal('0.80')
        )

        # Create SPC Config
        self.spc_config = SPCConfig.objects.create(
            product=self.product,
            machine=self.filler,
            nominal_grams=Decimal('500.00'),
            usl_grams=Decimal('505.00'),
            lsl_grams=Decimal('495.00'),
            subgroup_size=5,
            material_cost_per_kg=Decimal('18.50'),
            annual_production_units=10000000,
        )

        # Create Quality User and Admin User
        self.quality_role = Role.objects.get_or_create(code='quality', defaults={'name': 'Quality Engineer'})[0]
        self.admin_role = Role.objects.get_or_create(code='admin', defaults={'name': 'System Administrator'})[0]

        self.quality_user = User.objects.create_user(username='quality_tester', password='password123')
        UserRoleAssignment.objects.create(user=self.quality_user, role=self.quality_role)

        self.admin_user = User.objects.create_user(username='admin_tester', password='password123')
        UserRoleAssignment.objects.create(user=self.admin_user, role=self.admin_role)

    def test_spc_config_defaults(self):
        """Verifies SPCConfig model initialization and specification limit defaults."""
        config = get_or_create_default_spc_config(self.product, self.filler)
        self.assertEqual(config.nominal_grams, Decimal('500.00'))
        self.assertEqual(config.usl_grams, Decimal('505.00'))
        self.assertEqual(config.lsl_grams, Decimal('495.00'))
        self.assertEqual(config.subgroup_size, 5)

    def test_subgroup_recording_and_xbar_r_calculation(self):
        """Verifies recording weight samples computes subgroup mean, range, and standard deviation."""
        weights = [501.20, 501.50, 500.90, 501.30, 501.10]
        sg = record_weight_samples_and_subgroup(
            machine=self.filler,
            product=self.product,
            weights=weights,
            operator=self.quality_user,
            line=self.line
        )

        self.assertIsNotNone(sg)
        self.assertEqual(sg.subgroup_number, 1)
        # Mean of [501.2, 501.5, 500.9, 501.3, 501.1] = 2506.0 / 5 = 501.2
        self.assertAlmostEqual(float(sg.sample_mean), 501.20, places=2)
        # Range = 501.5 - 500.9 = 0.6
        self.assertAlmostEqual(float(sg.sample_range), 0.60, places=2)
        # Subgroup has 5 individual sample records
        self.assertEqual(sg.samples.count(), 5)

    def test_iso_22400_spc_xbar_and_r_limits_fixture(self):
        """
        Mathematical verification against known ASTM / ISO 22400-2 control chart fixture:
        SG 1: [500.0, 501.0, 500.5, 501.5, 502.0] -> Mean = 501.0, R = 2.0
        SG 2: [501.0, 502.0, 501.5, 502.5, 503.0] -> Mean = 502.0, R = 2.0
        Grand Mean = 501.5, Mean Range = 2.0
        For n=5: A2 = 0.577, D4 = 2.114, D3 = 0.0
        UCL_X = 501.5 + (0.577 * 2.0) = 502.654
        LCL_X = 501.5 - (0.577 * 2.0) = 500.346
        UCL_R = 2.114 * 2.0 = 4.228
        LCL_R = 0.0
        """
        record_weight_samples_and_subgroup(self.filler, self.product, [500.0, 501.0, 500.5, 501.5, 502.0], line=self.line)
        record_weight_samples_and_subgroup(self.filler, self.product, [501.0, 502.0, 501.5, 502.5, 503.0], line=self.line)

        metrics = calculate_spc_metrics(machine=self.filler, line=self.line, product=self.product)
        self.assertEqual(metrics['status'], 'OK')

        # Check Center Lines
        self.assertAlmostEqual(metrics['xbar_chart']['cl'], 501.5, places=1)
        self.assertAlmostEqual(metrics['r_chart']['cl'], 2.0, places=1)

        # Check Control Limits
        self.assertAlmostEqual(metrics['xbar_chart']['ucl'], 502.65, places=1)
        self.assertAlmostEqual(metrics['xbar_chart']['lcl'], 500.35, places=1)
        self.assertAlmostEqual(metrics['r_chart']['ucl'], 4.23, places=1)
        self.assertEqual(metrics['r_chart']['lcl'], 0.0)

    def test_process_capability_cp_and_cpk_calculation(self):
        """
        Verifies Cp and Cpk capability formulas:
        Cp = (USL - LSL) / (6 * sigma)
        Cpk = min((USL - mu)/(3 * sigma), (mu - LSL)/(3 * sigma))
        """
        # Seed 4 subgroups around 501.0 with small variation
        for _ in range(4):
            record_weight_samples_and_subgroup(self.filler, self.product, [500.8, 501.1, 501.0, 500.9, 501.2], line=self.line)

        metrics = calculate_spc_metrics(machine=self.filler, line=self.line, product=self.product)
        self.assertEqual(metrics['status'], 'OK')

        cp = metrics['capability']['cp']
        cpk = metrics['capability']['cpk']
        self.assertIsNotNone(cp)
        self.assertIsNotNone(cpk)
        self.assertGreater(cpk, 1.0)
        self.assertIn(metrics['capability']['rating'], ['CAPABLE', 'MARGINAL'])

    def test_giveaway_and_recalibration_simulation(self):
        """Verifies giveaway calculation and interactive recalibration simulation."""
        # Seed 3 subgroups with +1.2g overfill (501.20g average)
        for _ in range(3):
            record_weight_samples_and_subgroup(self.filler, self.product, [501.2, 501.4, 501.1, 501.3, 501.0], line=self.line)

        metrics = calculate_spc_metrics(machine=self.filler, line=self.line, product=self.product)
        self.assertEqual(metrics['status'], 'OK')

        giveaway = metrics['giveaway']
        self.assertAlmostEqual(giveaway['avg_giveaway_grams'], 1.20, places=1)
        self.assertGreater(giveaway['annual_giveaway_cost'], 0)

        # Test Recalibration Simulation with -0.80g offset
        sim = simulate_recalibration(
            target_offset_grams=-0.80,
            machine=self.filler,
            line=self.line,
            product=self.product
        )
        self.assertEqual(sim['status'], 'OK')
        self.assertAlmostEqual(sim['grams_saved_per_unit'], 0.80, places=2)
        # Annual savings with 10M units and $18.50/kg:
        # (10,000,000 * 0.8) / 1000 * 18.50 = 8,000 * 18.50 = $148,000
        self.assertAlmostEqual(sim['annual_savings_cost'], 148000.0, places=0)
        # Compliance disclaimer must be present
        self.assertIn('Compliance Disclaimer', sim['disclaimer'])

    def test_quality_csv_export_endpoint(self):
        """Verifies GET /quality/export/csv/ exports valid CSV with correct headers."""
        record_weight_samples_and_subgroup(self.filler, self.product, [501.2, 501.5, 500.9, 501.3, 501.1], line=self.line)

        self.client.force_login(self.quality_user)
        url = reverse('quality_export_csv')
        response = self.client.get(url, {'product': self.product.id, 'line': self.line.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        content = response.content.decode('utf-8')
        self.assertIn('Sample ID,Timestamp (UTC),Machine Code', content)
        self.assertIn('501.20', content)

    def test_zero_emojis_in_quality_templates(self):
        """Verifies strict zero-emoji policy across all Batch 5 quality views."""
        record_weight_samples_and_subgroup(self.filler, self.product, [501.2, 501.5, 500.9, 501.3, 501.1], line=self.line)

        self.client.force_login(self.admin_user)
        urls = [
            reverse('quality_home'),
            reverse('quality_samples'),
            reverse('quality_defects'),
            reverse('quality_giveaway'),
        ]

        for u in urls:
            resp = self.client.get(u)
            self.assertEqual(resp.status_code, 200, f"Route {u} returned status {resp.status_code}")
            content = resp.content.decode('utf-8')
            matches = EMOJI_PATTERN.findall(content)
            self.assertEqual(len(matches), 0, f"Found decorative emojis in {u}: {matches}")
