"""
Automated test suite verifying Batch 1 deliverables:
- Authentication & Dynamic Role Landing
- Multi-Role Persona Switching
- Strict Server-Side Role Authorization (403 Forbidden on Unauthorized Access)
- Bilingual & RTL Support
- Product Management CRUD & Archival (Section 2.4 Acceptance)
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import Role, UserRoleAssignment, AuditEvent
from apps.masterdata.models import Product, Factory, Line, Machine, Process

User = get_user_model()


class Batch1TestSuite(TestCase):
    """
    Comprehensive verification for Batch 1 requirements.
    """
    @classmethod
    def setUpTestData(cls):
        # 1. Canonical Roles
        cls.roles = {}
        role_definitions = [
            ('operator', 'Line Operator', '/operator/'),
            ('supervisor', 'Shift Supervisor', '/floor/'),
            ('maintenance', 'Maintenance Technician', '/maintenance/'),
            ('quality', 'Quality Specialist', '/quality/'),
            ('planner', 'Production Planner', '/planning/products/'),
            ('supply_chain', 'Supply Chain Officer', '/work-orders/'),
            ('manager', 'Plant Director', '/dashboard/'),
            ('admin', 'System Administrator', '/administration/'),
            ('controller', 'Simulator Controller', '/controller/'),
        ]
        for code, name, landing in role_definitions:
            r, _ = Role.objects.get_or_create(
                code=code,
                defaults={'name': name, 'name_ar': name, 'default_landing': landing}
            )
            cls.roles[code] = r

        # 2. Master Plant Data
        cls.factory = Factory.objects.create(code='TEST-PLANT-01', name='Test Factory')
        cls.line = Line.objects.create(factory=cls.factory, code='LINE-01', name='Test Line 1')
        cls.machine = Machine.objects.create(line=cls.line, code='FL-01', name='Test Filler', is_bottleneck=True)

        # 3. Single-Role Demo Users
        cls.users = {}
        for code in cls.roles.keys():
            u = User.objects.create_user(
                username=f"{code}_test",
                password="TestPassword@123",
                first_name=code.capitalize(),
                last_name="Tester",
                is_staff=(code == 'admin'),
                is_superuser=(code == 'admin'),
            )
            UserRoleAssignment.objects.create(
                user=u,
                role=cls.roles[code],
                factory=cls.factory,
                line=cls.line,
                is_active=True
            )
            cls.users[code] = u

        # 4. Multi-Role User (Lead Tech: Supervisor + Maintenance)
        cls.lead_tech = User.objects.create_user(
            username="lead_tech_test",
            password="TestPassword@123",
            first_name="Lead",
            last_name="Tech"
        )
        UserRoleAssignment.objects.create(user=cls.lead_tech, role=cls.roles['supervisor'], is_active=True)
        UserRoleAssignment.objects.create(user=cls.lead_tech, role=cls.roles['maintenance'], is_active=True)

        # 5. Seed Test Product
        cls.product = Product.objects.create(
            factory=cls.factory,
            code='SKU-TEST-500',
            name='Test Mineral Water 500ml',
            name_ar='مياه اختبار 500 مل',
            category='Bottled Water',
            unit_of_measure='Bottle',
            sop_document_title='DOC-TEST-REV1.pdf',
            ideal_cycle_time_sec=Decimal('0.50'),
            rated_speed_cpm=120,
        )

    def setUp(self):
        self.client = Client()

    # --------------------------------------------------------------------------
    # 1. Role Verification
    # --------------------------------------------------------------------------
    def test_all_9_canonical_roles_exist(self):
        """Verify that all 9 canonical roles are registered (with engineering removed)."""
        expected_codes = [
            'operator', 'supervisor', 'maintenance', 'quality',
            'planner', 'supply_chain', 'manager', 'admin', 'controller'
        ]
        existing_codes = list(Role.objects.values_list('code', flat=True))
        for code in expected_codes:
            self.assertIn(code, existing_codes, f"Canonical role '{code}' must exist in database.")
        self.assertNotIn('engineer', existing_codes, "Role 'engineer' must not exist in canonical roles.")

    # --------------------------------------------------------------------------
    # 2. Authentication & Dynamic Landing Page Resolution
    # --------------------------------------------------------------------------
    def test_login_and_dynamic_role_landing_resolution(self):
        """
        Verify that logging in dynamically resolves the landing page according to
        the user's assigned role persona without rigid if-elif cascades.
        """
        test_cases = [
            ('operator', '/operator/'),
            ('supervisor', '/floor/'),
            ('maintenance', '/maintenance/'),
            ('quality', '/quality/'),
            ('planner', '/planning/products/'),
            ('supply_chain', '/work-orders/'),
            ('manager', '/dashboard/'),
            ('admin', '/administration/'),
            ('controller', '/controller/'),
        ]

        for role_code, expected_landing in test_cases:
            user = self.users[role_code]
            client = Client()
            login_success = client.login(username=user.username, password="TestPassword@123")
            self.assertTrue(login_success, f"Login must succeed for {user.username}")

            response = client.get(reverse('role_landing'), follow=False)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(
                response.url, expected_landing,
                f"Role '{role_code}' must dynamically land on '{expected_landing}', got '{response.url}'"
            )

    # --------------------------------------------------------------------------
    # 3. Multi-Role Switching (Section 3.1)
    # --------------------------------------------------------------------------
    def test_multi_role_persona_switching_without_relogin(self):
        """
        Verify that a user with multiple roles (lead_tech) can switch personas
        without logging out, and their active persona, home, and navigation update.
        """
        self.client.login(username="lead_tech_test", password="TestPassword@123")

        # Initial landing defaults to supervisor
        response = self.client.get(reverse('role_landing'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get('active_role'), 'supervisor')

        # Switch persona to maintenance
        switch_resp = self.client.post(reverse('switch_role'), {'role_code': 'maintenance'}, follow=True)
        self.assertEqual(switch_resp.status_code, 200)
        self.assertEqual(self.client.session.get('active_role'), 'maintenance')

        # Verify landing is now maintenance
        landing_resp = self.client.get(reverse('role_landing'), follow=False)
        self.assertEqual(landing_resp.url, '/maintenance/')

        # Verify audit trail records persona switch
        audit = AuditEvent.objects.filter(actor=self.lead_tech, action='SWITCH_PERSONA').first()
        self.assertIsNotNone(audit, "Persona switch must be audited.")
        self.assertEqual(audit.active_role, 'maintenance')

    def test_unauthorized_role_switch_denied(self):
        """
        Verify that attempting to switch to an unassigned role is rejected.
        """
        self.client.login(username="lead_tech_test", password="TestPassword@123")

        # Attempt to switch to 'admin' (which lead_tech does NOT have)
        response = self.client.post(reverse('switch_role'), {'role_code': 'admin'}, follow=False)
        # Should NOT switch
        self.assertNotEqual(self.client.session.get('active_role'), 'admin')

    # --------------------------------------------------------------------------
    # 4. Strict Server-Side Authorization Enforcement (Backend + UI)
    # --------------------------------------------------------------------------
    def test_operator_cannot_access_manager_dashboard(self):
        """Operator accessing /dashboard/ must receive HTTP 403 Forbidden."""
        self.client.login(username="operator_test", password="TestPassword@123")
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 403)

    def test_operator_cannot_access_administration(self):
        """Operator accessing /administration/ must receive HTTP 403 Forbidden."""
        self.client.login(username="operator_test", password="TestPassword@123")
        response = self.client.get('/administration/')
        self.assertEqual(response.status_code, 403)

    def test_quality_cannot_access_controller(self):
        """Quality specialist accessing /controller/ must receive HTTP 403 Forbidden."""
        self.client.login(username="quality_test", password="TestPassword@123")
        response = self.client.get('/controller/')
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_request_redirects_to_login(self):
        """Unauthenticated direct access to protected view redirects to login."""
        response = self.client.get('/floor/', follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    # --------------------------------------------------------------------------
    # 5. Bilingual Support & RTL Context
    # --------------------------------------------------------------------------
    def test_bilingual_language_switching_and_rtl(self):
        """Verify that language switcher toggles between English and Arabic with RTL."""
        self.client.login(username="planner_test", password="TestPassword@123")

        # Switch to Arabic
        response = self.client.get(reverse('set_language') + '?lang=ar', follow=True)
        self.assertEqual(self.client.session.get('django_language'), 'ar')

        # Load page in Arabic
        page_resp = self.client.get(reverse('products_list'))
        self.assertEqual(page_resp.status_code, 200)
        self.assertContains(page_resp, 'dir="rtl"')
        self.assertContains(page_resp, 'إدارة المنتجات')

        # Switch back to English
        self.client.get(reverse('set_language') + '?lang=en', follow=True)
        page_resp_en = self.client.get(reverse('products_list'))
        self.assertEqual(page_resp_en.status_code, 200)
        self.assertContains(page_resp_en, 'dir="ltr"')
        self.assertContains(page_resp_en, 'Product Management')

    # --------------------------------------------------------------------------
    # 6. Product Management Acceptance (Section 2.4 Reference Specification)
    # --------------------------------------------------------------------------
    def test_product_management_page_and_archival(self):
        """
        Verify reference acceptance:
        - Planner can view products list
        - Add product form
        - Archival preserves historical record rather than deleting
        """
        self.client.login(username="planner_test", password="TestPassword@123")

        # 1. View products page
        resp = self.client.get(reverse('products_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'SKU-TEST-500')
        self.assertContains(resp, 'Add Product')

        # 2. Add a new product
        add_resp = self.client.post(reverse('product_add'), {
            'code': 'SKU-NEW-330',
            'name': 'New Cola 330ml',
            'name_ar': 'كولا جديدة 330 مل',
            'category': 'Carbonated Drinks',
            'unit_of_measure': 'Can',
            'ideal_cycle_time_sec': '0.40',
            'rated_speed_cpm': '150',
            'sop_document_title': 'SOP-NEW-REV1.pdf',
        }, follow=True)
        self.assertEqual(add_resp.status_code, 200)

        created_prod = Product.objects.filter(code='SKU-NEW-330').first()
        self.assertIsNotNone(created_prod)
        self.assertEqual(created_prod.name, 'New Cola 330ml')
        self.assertEqual(created_prod.rated_speed_cpm, 150)

        # 3. Archive product (Section 2.4: archive with referenced history preserved)
        archive_resp = self.client.post(
            reverse('product_archive', kwargs={'product_id': created_prod.id}),
            follow=True
        )
        self.assertEqual(archive_resp.status_code, 200)
        created_prod.refresh_from_db()
        self.assertTrue(created_prod.is_archived, "Archived product must remain in database with is_archived=True.")
