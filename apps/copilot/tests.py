"""
Automated Test Suite for FactSense Industrial AI Copilot (F09).
Verifies:
1. Dual-Engine architecture (Cloud Gemini + Edge Offline Heuristics).
2. Bilingual understanding and contextual responses (English & Arabic).
3. Context-aware queries (OEE drag, bottleneck identification, 4-bullet handover synthesis, giveaway financial losses).
4. Clickable interactive action chips linking to authorized operational pages.
5. 1-Sentence quick executive summary endpoint.
6. RBAC enforcement and zero-emoji compliance.
"""

import re
import json
from decimal import Decimal
from datetime import time
from django.test import TestCase, Client
from apps.accounts.models import User, Role, UserRoleAssignment
from apps.masterdata.models import Factory, Line, Machine, Product, Shift
from apps.telemetry.models import MachineCurrentState
from apps.copilot.models import CopilotChatSession, CopilotChatMessage
from apps.copilot.services.dual_engine import (
    ask_industrial_copilot, get_quick_executive_summary, collect_factory_context
)

EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff]|[\u2600-\u27BF]|[\u2300-\u23FF]|[\u2B50-\u2B55]|[\u203C\u2049\u2122\u2139\u24C2]"
)


class CopilotEngineTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Factory, Line & Bottleneck Machine
        self.factory = Factory.objects.create(code='FAC-COPILOT', name='Bottling Plant 1')
        self.line = Line.objects.create(factory=self.factory, code='LINE-COP-01', name='High Speed Water Line')
        
        self.bottleneck = Machine.objects.create(
            line=self.line,
            code='FL-30-COP',
            name='Rotary Filler FL-30',
            category='FILLER',
            ideal_run_rate_cpm=120.0,
            sequence_order=3,
            is_bottleneck=True
        )
        self.line.bottleneck_machine = self.bottleneck
        self.line.save()

        # Telemetry State for Bottleneck
        MachineCurrentState.objects.create(
            machine=self.bottleneck,
            state_code='RUNNING',
            current_speed_cpm=105.0,
            temperature_c=68.5,
            vibration_rms=2.1
        )

        # Shift
        self.shift = Shift.objects.create(
            factory=self.factory,
            code='SHIFT-1',
            name='Morning Shift',
            start_time=time(7, 0),
            end_time=time(15, 0),
            sequence=1
        )

        # Product
        self.product = Product.objects.create(
            factory=self.factory,
            code='PRD-WTR-500',
            name='500ml Bottled Water',
            nominal_weight=Decimal('500.00'),
            unit_cost=Decimal('1.50'),
            scrap_cost=Decimal('0.80')
        )
        self.line.current_product = self.product
        self.line.save()

        # User & Roles
        self.supervisor_role, _ = Role.objects.get_or_create(code='supervisor', defaults={'name': 'Supervisor'})
        self.operator_role, _ = Role.objects.get_or_create(code='operator', defaults={'name': 'Operator'})

        self.supervisor_user = User.objects.create_user(username='copilot_super', password='password123')
        UserRoleAssignment.objects.create(user=self.supervisor_user, role=self.supervisor_role, is_active=True)

        self.operator_user = User.objects.create_user(username='copilot_op', password='password123')
        UserRoleAssignment.objects.create(user=self.operator_user, role=self.operator_role, is_active=True)

    def _login(self, user, role_code):
        self.client.login(username=user.username, password='password123')
        s = self.client.session
        s['active_role'] = role_code
        s.save()

    def test_english_queries_and_action_chips(self):
        """Verify English intent parsing for OEE, bottleneck, giveaway, and handover."""
        # 1. OEE Query
        res_oee = ask_industrial_copilot("Why is OEE low on Line 1 today?", line=self.line)
        self.assertEqual(res_oee['language'], 'en')
        self.assertIn("Overall Equipment Effectiveness", res_oee['answer'])
        self.assertIn("Rotary Filler FL-30", res_oee['answer'])
        self.assertGreater(len(res_oee['action_chips']), 0)
        self.assertTrue(any('/stoppages/' in c['url'] for c in res_oee['action_chips']))

        # 2. Bottleneck Query
        res_btn = ask_industrial_copilot("Which machine is the active bottleneck?", line=self.line)
        self.assertIn("Rotary Filler FL-30", res_btn['answer'])
        self.assertIn("105 CPM", res_btn['answer'])
        self.assertIn("120", res_btn['answer'])
        self.assertTrue(any('/operator/' in c['url'] for c in res_btn['action_chips']))

        # 3. Shift Handover Synthesis Query
        res_ho = ask_industrial_copilot("Draft shift handover notes for the incoming supervisor.", line=self.line)
        self.assertIn("Official 4-Bullet Shift Handover Executive Synthesis", res_ho['answer'])
        self.assertIn("1.", res_ho['answer'])
        self.assertIn("4.", res_ho['answer'])
        self.assertTrue(any('/reports/export/pdf/' in c['url'] for c in res_ho['action_chips']))

        # 4. Giveaway Loss Query
        res_gw = ask_industrial_copilot("How much did overfill giveaway cost us this morning?", line=self.line)
        self.assertIn("Overfill Product Giveaway Financial Assessment", res_gw['answer'])
        self.assertIn("$", res_gw['answer'])
        self.assertTrue(any('/quality/giveaway/' in c['url'] for c in res_gw['action_chips']))

        # Check zero emojis in all responses
        for r in [res_oee, res_btn, res_ho, res_gw]:
            self.assertFalse(bool(EMOJI_PATTERN.search(r['answer'])))

    def test_arabic_queries_and_action_chips(self):
        """Verify Arabic intent parsing for OEE, bottleneck, and shift handover synthesis."""
        # 1. Arabic OEE Query
        res_ar_oee = ask_industrial_copilot("لماذا انخفضت كفاءة الخط الأول اليوم؟", line=self.line)
        self.assertEqual(res_ar_oee['language'], 'ar')
        self.assertIn("الكفاءة الإجمالية", res_ar_oee['answer'])
        self.assertIn("الماكينة الخانقة", res_ar_oee['answer'])
        self.assertGreater(len(res_ar_oee['action_chips']), 0)

        # 2. Arabic Bottleneck Query
        res_ar_btn = ask_industrial_copilot("ما هي الماكينة الخانقة حالياً وما سرعتها؟", line=self.line)
        self.assertEqual(res_ar_btn['language'], 'ar')
        self.assertIn("الماكينة الخانقة المحددة", res_ar_btn['answer'])
        self.assertIn("Rotary Filler FL-30", res_ar_btn['answer'])

        # 3. Arabic Shift Handover Synthesis Query
        res_ar_ho = ask_industrial_copilot("صغ محضر تسليم الوردية للمشرف القادم", line=self.line)
        self.assertEqual(res_ar_ho['language'], 'ar')
        self.assertIn("محضر تسليم الوردية التنفيذي", res_ar_ho['answer'])
        self.assertIn("1. الإنتاج والكفاءة", res_ar_ho['answer'])

        # Check zero emojis in Arabic responses
        for r in [res_ar_oee, res_ar_btn, res_ar_ho]:
            self.assertFalse(bool(EMOJI_PATTERN.search(r['answer'])))

    def test_quick_executive_summary_function(self):
        """Verify 1-sentence executive summary returns valid status level and text."""
        summary_en = get_quick_executive_summary(line=self.line, lang='en')
        self.assertIn(summary_en['status_level'], ['OPTIMAL', 'WARNING', 'CRITICAL'])
        self.assertIn(self.line.name, summary_en['summary_text'])

        summary_ar = get_quick_executive_summary(line=self.line, lang='ar')
        self.assertIn(summary_ar['status_level'], ['OPTIMAL', 'WARNING', 'CRITICAL'])

    def test_copilot_chat_api_and_rbac(self):
        """Verify POST /copilot/api/chat/ records message in session and enforces RBAC."""
        self._login(self.supervisor_user, 'supervisor')

        resp = self.client.post(
            '/copilot/api/chat/',
            data=json.dumps({'query': 'Which machine is the bottleneck?', 'line_id': str(self.line.id)}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('Rotary Filler FL-30', data['answer'])
        self.assertGreater(len(data['action_chips']), 0)

        # Verify recorded session and turns
        session = CopilotChatSession.objects.filter(id=data['session_id']).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.messages.count(), 2)  # 1 user + 1 assistant

        # Verify Operator role is blocked with HTTP 403
        self._login(self.operator_user, 'operator')
        resp_blocked = self.client.post(
            '/copilot/api/chat/',
            data=json.dumps({'query': 'OEE status'}),
            content_type='application/json'
        )
        self.assertEqual(resp_blocked.status_code, 403)
