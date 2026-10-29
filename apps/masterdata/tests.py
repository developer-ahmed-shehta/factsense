import re
from datetime import time
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User, Role, UserRoleAssignment, AuditEvent
from apps.masterdata.models import (
    Product, Process, Factory, Line, Machine, Shift,
    PlannedBreak, KioskDevice, ReasonCategory, StoppageReason,
    DefectReason, MachineProductRate
)

EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff]|[\u2600-\u27BF]|[\u2300-\u23FF]|[\u2B50-\u2B55]|[\u203C\u2049\u2122\u2139\u24C2]"
)


class MasterdataI18nTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Seed roles
        self.planner_role, _ = Role.objects.get_or_create(
            code='planner',
            defaults={
                'name': 'Production Planner',
                'name_ar': 'مخطط إنتاج',
                'default_landing': '/planning/products/'
            }
        )
        self.operator_role, _ = Role.objects.get_or_create(
            code='operator',
            defaults={
                'name': 'Line Operator',
                'name_ar': 'مشغل ماكينة',
                'default_landing': '/operator/machine/'
            }
        )

        # Seed user
        self.planner_user = User.objects.create_user(
            username='test_planner',
            password='testpassword123',
            first_name='Test',
            last_name='Planner',
            preferred_language='en'
        )
        UserRoleAssignment.objects.create(
            user=self.planner_user,
            role=self.planner_role,
            is_active=True
        )

        # Seed product & process
        self.proc1 = Process.objects.create(
            code='MILLING',
            name='Precision Milling',
            name_ar='التفريز الدقيق',
            sequence_order=1
        )
        self.product = Product.objects.create(
            code='PRD-101',
            name='Hydraulic Valve Shaft',
            name_ar='عمود الصمام الهيدروليكي',
            category='Hydraulics',
            unit_of_measure='PCS',
            ideal_cycle_time_sec=2.5,
            sop_document_url='https://cad.factsense.internal/drawings/PRD-101'
        )
        self.product.processes.add(self.proc1)

    def test_english_products_page_renders_from_locale(self):
        """Verify English page loads strings from locale/en/LC_MESSAGES/django.mo"""
        self.client.login(username='test_planner', password='testpassword123')
        session = self.client.session
        session['active_role'] = 'planner'
        session['django_language'] = 'en'
        session.save()

        response = self.client.get('/planning/products/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Check LTR
        self.assertIn('dir="ltr"', content)
        self.assertIn('lang="en"', content)

        # Check English strings from locale/
        self.assertIn('Product Management', content)
        self.assertIn('Add Product', content)
        self.assertIn('DESIGN LINK', content)
        self.assertIn('Hydraulic Valve Shaft', content)

        # Assert ZERO emojis
        self.assertFalse(bool(EMOJI_PATTERN.search(content)), "Found emoji in English page HTML!")

    def test_arabic_products_page_renders_from_locale(self):
        """Verify Arabic page loads translations from locale/ar/LC_MESSAGES/django.mo"""
        self.client.login(username='test_planner', password='testpassword123')
        session = self.client.session
        session['active_role'] = 'planner'
        session['django_language'] = 'ar'
        session.save()

        # Also set the language cookie
        self.client.cookies['factsense_language'] = 'ar'

        response = self.client.get('/planning/products/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Check RTL
        self.assertIn('dir="rtl"', content)
        self.assertIn('lang="ar"', content)

        # Check Arabic strings from locale/
        self.assertIn('إدارة المنتجات', content)
        self.assertIn('إضافة منتج', content)
        self.assertIn('اسم المنتج', content)
        self.assertIn('رابط التصميم', content)
        self.assertIn('تسجيل الخروج', content)

        # Assert ZERO emojis
        self.assertFalse(bool(EMOJI_PATTERN.search(content)), "Found emoji in Arabic page HTML!")

    def test_language_switch_endpoint(self):
        """Verify GET /accounts/set-language/?lang=ar updates cookie and redirects"""
        response = self.client.get('/accounts/set-language/?lang=ar', HTTP_REFERER='/planning/products/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/planning/products/')
        self.assertEqual(self.client.session.get('django_language'), 'ar')


class Batch2MasterdataTestSuite(TestCase):
    """
    Automated test verification suite for Batch 2 Deliverables:
    - 60-Second Onboarding Wizard with Industry Presets (Water, CSD, Oil)
    - Interactive Factory Topology Hub & SVG Node Graph with RTL Directional Flow
    - Kiosk Hardware Pairing & Gateway Claim QR Onboarding
    - Shift Lifecycle & Planned Break Production Time Accounting (ISO 22400)
    - MachineProductRate Speed Matrix Operations
    - Stoppage & Defect Taxonomies with TPM Mapping
    - Strict Server-Side Role-Based Access Control (RBAC 403)
    - Zero Emojis Validation
    """

    def setUp(self):
        self.client = Client()

        # Seed canonical roles
        self.roles = {}
        for rcode, rname, land in [
            ('planner', 'Production Planner', '/planning/products/'),
            ('admin', 'System Administrator', '/administration/'),
            ('supervisor', 'Shift Supervisor', '/floor/'),
            ('operator', 'Line Operator', '/operator/'),
            ('quality', 'Quality Specialist', '/quality/'),
        ]:
            r, _ = Role.objects.get_or_create(
                code=rcode,
                defaults={'name': rname, 'name_ar': rname, 'default_landing': land}
            )
            self.roles[rcode] = r

        # Factory
        self.factory = Factory.objects.create(
            code='CAIRO-FACILITY-01',
            name='Cairo Packaging Site',
            name_ar='مصنع تعبئة القاهرة',
            industry='Beverage / Bottling',
            timezone='Africa/Cairo',
        )

        # Users
        self.planner_user = User.objects.create_user(
            username='planner_tester',
            password='TestPassword@123',
            preferred_language='en'
        )
        UserRoleAssignment.objects.create(
            user=self.planner_user,
            role=self.roles['planner'],
            factory=self.factory,
            is_active=True
        )

        self.operator_user = User.objects.create_user(
            username='operator_tester',
            password='TestPassword@123',
            preferred_language='en'
        )
        UserRoleAssignment.objects.create(
            user=self.operator_user,
            role=self.roles['operator'],
            factory=self.factory,
            is_active=True
        )

    def _login_as(self, user, role_code):
        self.client.login(username=user.username, password='TestPassword@123')
        session = self.client.session
        session['active_role'] = role_code
        session['django_language'] = 'en'
        session.save()

    def test_onboarding_wizard_water_preset(self):
        """Verify 60-Second Onboarding Wizard deploys complete Water line with 7 machines and bottleneck."""
        self._login_as(self.planner_user, 'planner')

        response = self.client.post('/masterdata/wizard/', {
            'preset_key': 'WATER',
            'line_code': 'LINE-WTR-TEST',
            'line_name': 'Test Bottled Water Line 01',
            'factory_id': str(self.factory.id),
            'target_oee': '85.0',
        })

        # Should redirect to topology viewer
        self.assertEqual(response.status_code, 302)
        self.assertIn('topology/?line_id=', response.url)

        # Verify Line created
        line = Line.objects.get(code='LINE-WTR-TEST')
        self.assertEqual(line.name, 'Test Bottled Water Line 01')
        self.assertEqual(line.target_oee, 85.0)

        # Verify 7 sequential machines
        machines = line.machines.all().order_by('sequence_order')
        self.assertEqual(machines.count(), 7)

        # Verify designated bottleneck machine is FL-30
        bottleneck = line.bottleneck_machine
        self.assertIsNotNone(bottleneck)
        self.assertEqual(bottleneck.code, 'LINE-WTR-TEST-FL-30')
        self.assertTrue(bottleneck.is_bottleneck)
        self.assertEqual(bottleneck.ideal_run_rate_cpm, 120.0)
        self.assertEqual(bottleneck.criticality_rank, 'A')

        # Verify default product created
        product = line.current_product
        self.assertIsNotNone(product)
        self.assertEqual(product.code, 'LINE-WTR-TEST-SKU-WTR-500ML')
        self.assertEqual(product.nominal_weight, Decimal('500.00'))

        # Verify MachineProductRate matrix entries exist for all 7 machines
        rates = MachineProductRate.objects.filter(product=product)
        self.assertEqual(rates.count(), 7)

        # Verify Kiosk device enrolled for bottleneck machine
        kiosk = KioskDevice.objects.filter(machine=bottleneck).first()
        self.assertIsNotNone(kiosk)
        self.assertEqual(kiosk.status, 'ACTIVE')
        self.assertTrue(kiosk.is_exclusive)

        # Verify audit trail
        audit = AuditEvent.objects.filter(action='WIZARD_DEPLOY_LINE', resource_id=str(line.id)).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.details['preset'], 'WATER')

    def test_onboarding_wizard_csd_and_oil_presets(self):
        """Verify CSD and Oil presets deploy correctly."""
        self._login_as(self.planner_user, 'planner')

        # Deploy CSD Line
        resp_csd = self.client.post('/masterdata/wizard/', {
            'preset_key': 'CSD',
            'line_code': 'LINE-CSD-TEST',
            'line_name': 'Test CSD Line',
            'factory_id': str(self.factory.id),
            'target_oee': '82.0',
        })
        self.assertEqual(resp_csd.status_code, 302)
        line_csd = Line.objects.get(code='LINE-CSD-TEST')
        self.assertEqual(line_csd.machines.count(), 5)
        self.assertEqual(line_csd.bottleneck_machine.code, 'LINE-CSD-TEST-FL-20')
        self.assertEqual(line_csd.bottleneck_machine.ideal_run_rate_cpm, 150.0)

        # Deploy Oil Line
        resp_oil = self.client.post('/masterdata/wizard/', {
            'preset_key': 'OIL',
            'line_code': 'LINE-OIL-TEST',
            'line_name': 'Test Oil Line',
            'factory_id': str(self.factory.id),
            'target_oee': '80.0',
        })
        self.assertEqual(resp_oil.status_code, 302)
        line_oil = Line.objects.get(code='LINE-OIL-TEST')
        self.assertEqual(line_oil.machines.count(), 4)
        self.assertEqual(line_oil.bottleneck_machine.code, 'LINE-OIL-TEST-FL-10')
        self.assertEqual(line_oil.bottleneck_machine.ideal_run_rate_cpm, 90.0)

    def test_topology_view_ltr_and_rtl_directional_flip(self):
        """Verify SVG Topology Graph renders conveyor nodes and flips sequence direction in RTL."""
        # Setup a line with 3 machines
        line = Line.objects.create(factory=self.factory, code='LINE-TOPO', name='Topology Line', sequence=1)
        m1 = Machine.objects.create(line=line, code='M1', name='Machine 1', sequence_order=10, ideal_run_rate_cpm=100)
        m2 = Machine.objects.create(line=line, code='M2', name='Machine 2 (Bottleneck)', sequence_order=20, ideal_run_rate_cpm=80, is_bottleneck=True)
        m3 = Machine.objects.create(line=line, code='M3', name='Machine 3', sequence_order=30, ideal_run_rate_cpm=120)
        line.bottleneck_machine = m2
        line.save()

        # 1. English (LTR)
        self._login_as(self.planner_user, 'planner')
        resp_en = self.client.get(f'/masterdata/topology/?line_id={line.id}')
        self.assertEqual(resp_en.status_code, 200)
        content_en = resp_en.content.decode('utf-8')
        self.assertIn('BOTTLENECK', content_en)
        self.assertIn('conveyor-flow', content_en)
        self.assertIn('dir="ltr"', content_en)
        self.assertFalse(bool(EMOJI_PATTERN.search(content_en)))

        # 2. Arabic (RTL)
        session = self.client.session
        session['django_language'] = 'ar'
        session.save()
        self.client.cookies['factsense_language'] = 'ar'

        resp_ar = self.client.get(f'/masterdata/topology/?line_id={line.id}')
        self.assertEqual(resp_ar.status_code, 200)
        content_ar = resp_ar.content.decode('utf-8')
        self.assertIn('dir="rtl"', content_ar)
        self.assertIn('مخطط طوبولوجيا', content_ar)
        self.assertFalse(bool(EMOJI_PATTERN.search(content_ar)))

    def test_kiosk_device_pairing(self):
        """Verify Kiosk device pairing action binds machine and records pairing timestamp."""
        self._login_as(self.planner_user, 'planner')
        line = Line.objects.create(factory=self.factory, code='LINE-K', name='Kiosk Line')
        mach = Machine.objects.create(line=line, code='K-MACH-01', name='Kiosk Machine 1', sequence_order=10)

        response = self.client.post('/masterdata/kiosk-pairing/claim/', {
            'claim_code': 'PAIR-TEST-99',
            'machine_id': str(mach.id),
            'device_name': 'Operator Tablet Samsung Active3',
        })
        self.assertEqual(response.status_code, 302)

        # Check device is now active and bound to mach
        kiosk = KioskDevice.objects.get(claim_code='PAIR-TEST-99')
        self.assertEqual(kiosk.machine, mach)
        self.assertEqual(kiosk.status, 'ACTIVE')
        self.assertIsNotNone(kiosk.paired_at)

        # Check audit event
        audit = AuditEvent.objects.filter(action='DEVICE_PAIR', resource_id=str(kiosk.id)).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.details['claim_code'], 'PAIR-TEST-99')

    def test_shift_schedule_planned_production_time_calculation(self):
        """Verify ISO 22400 Planned Production Time calculation with scheduled window minus unpaid breaks."""
        # 1. Standard Day Shift: 07:00 to 15:00 = 8 hours = 480 minutes
        shift_day = Shift.objects.create(
            factory=self.factory,
            code='SHIFT-DAY-TEST',
            name='Day Shift Test',
            start_time=time(7, 0),
            end_time=time(15, 0),
            unpaid_break_minutes=30,
            sequence=1
        )
        self.assertEqual(shift_day.total_scheduled_minutes, 480)
        # Without explicit break models, uses unpaid_break_minutes = 30 -> 450 min
        self.assertEqual(shift_day.planned_operating_minutes, 450)

        # Add explicit PlannedBreaks: Morning Tea (15 min) + Lunch (30 min) = 45 min
        PlannedBreak.objects.create(
            shift=shift_day,
            name='Morning Tea',
            start_time=time(9, 30),
            end_time=time(9, 45),
            duration_minutes=15,
            is_unpaid=True
        )
        PlannedBreak.objects.create(
            shift=shift_day,
            name='Lunch Break',
            start_time=time(12, 30),
            end_time=time(13, 0),
            duration_minutes=30,
            is_unpaid=True
        )
        # 480 - 45 = 435 minutes
        self.assertEqual(shift_day.planned_operating_minutes, 435)

        # 2. Cross-Midnight Shift: 23:00 to 07:00 next day = 8 hours = 480 minutes
        shift_night = Shift.objects.create(
            factory=self.factory,
            code='SHIFT-NIGHT-TEST',
            name='Night Shift Test',
            start_time=time(23, 0),
            end_time=time(7, 0),
            unpaid_break_minutes=30,
            sequence=2
        )
        self.assertEqual(shift_night.total_scheduled_minutes, 480)
        self.assertEqual(shift_night.planned_operating_minutes, 450)

    def test_speed_matrix_update(self):
        """Verify MachineProductRate speed matrix updates CPM and recalculates cycle time."""
        self._login_as(self.planner_user, 'planner')
        line = Line.objects.create(factory=self.factory, code='LINE-R', name='Rate Line')
        mach = Machine.objects.create(line=line, code='R-M1', name='Rate Mach 1', sequence_order=10)
        prod = Product.objects.create(factory=self.factory, code='R-P1', name='Rate Prod 1')

        response = self.client.post('/masterdata/rates/update/', {
            'machine_id': str(mach.id),
            'product_id': str(prod.id),
            'rated_speed_cpm': '150.0',
            'ideal_cycle_time_sec': '',  # auto-calc 60 / 150 = 0.40s
        })
        self.assertEqual(response.status_code, 302)

        rate = MachineProductRate.objects.get(machine=mach, product=prod)
        self.assertEqual(rate.rated_speed_cpm, 150.0)
        self.assertEqual(rate.ideal_cycle_time_sec, 0.40)

    def test_stoppage_and_defect_taxonomies(self):
        """Verify Stoppage and Defect taxonomies create with TPM mapping and default disposition."""
        cat = ReasonCategory.objects.create(name='Mechanical', department='MECHANICAL')
        stop = StoppageReason.objects.create(
            category=cat,
            code='TEST_JAM',
            name='Test Jam',
            tpm_loss_type='AVAILABILITY_BREAKDOWN',
            standard_resolution_min=25
        )
        self.assertEqual(stop.tpm_loss_type, 'AVAILABILITY_BREAKDOWN')

        defect = DefectReason.objects.create(
            code='TEST_LEAK',
            name='Test Leak',
            category='Capping',
            default_disposition='QUARANTINE'
        )
        self.assertEqual(defect.default_disposition, 'QUARANTINE')

    def test_rbac_operator_blocked_from_wizard_and_machines_management(self):
        """Verify Operator receives HTTP 403 Forbidden when trying to access admin/planner configuration."""
        self._login_as(self.operator_user, 'operator')

        # Direct access to wizard should be blocked
        resp_wiz = self.client.get('/masterdata/wizard/')
        self.assertEqual(resp_wiz.status_code, 403)

        # Direct access to add machine should be blocked
        resp_mach = self.client.post('/masterdata/machines/add/', {})
        self.assertEqual(resp_mach.status_code, 403)

    def test_zero_emojis_in_batch_2_views(self):
        """Assert zero emojis rendered in any Batch 2 HTML templates."""
        self._login_as(self.planner_user, 'planner')

        urls = [
            '/masterdata/wizard/',
            '/masterdata/topology/',
            '/masterdata/machines/',
            '/masterdata/rates/',
            '/shifts/',
            '/planning/reasons/',
            '/planning/processes/',
            '/masterdata/kiosk-pairing/',
        ]
        for url in urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"URL {url} returned non-200 status {resp.status_code}")
            content = resp.content.decode('utf-8')
            self.assertFalse(bool(EMOJI_PATTERN.search(content)), f"Found emoji in URL {url}!")

