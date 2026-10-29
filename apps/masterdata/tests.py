import re
from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User, Role, UserRoleAssignment
from apps.masterdata.models import Product, Process

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
