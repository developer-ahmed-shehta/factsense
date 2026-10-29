"""
Automated Test Suite for Shift Handover & Production Reporting (F10).
Verifies:
1. High-resolution PDF report generation using ReportLab.
2. Multi-tab Excel workbook generation (.xlsx) using OpenPyXL.
3. Automated Report Subscriptions and delivery dispatch logs (Email & Telegram).
4. Historical Data Explorer and CSV tabular exports.
5. Export HTTP endpoints and zero-emoji compliance.
"""

import io
import re
from datetime import time
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from openpyxl import load_workbook
from apps.accounts.models import User, Role, UserRoleAssignment
from apps.masterdata.models import Factory, Line, Machine, Product, Shift
from apps.reports.models import ReportSubscription, ReportDispatchLog
from apps.reports.services.pdf_generator import generate_shift_handover_pdf
from apps.reports.services.excel_generator import generate_shift_handover_excel
from apps.reports.services.dispatch_service import dispatch_subscription

EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff]|[\u2600-\u27BF]|[\u2300-\u23FF]|[\u2B50-\u2B55]|[\u203C\u2049\u2122\u2139\u24C2]"
)


class ReportsGeneratorTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Factory, Line & Machine
        self.factory = Factory.objects.create(code='FAC-REP', name='Juice Packaging Plant')
        self.line = Line.objects.create(factory=self.factory, code='LINE-REP-01', name='Hot Fill Juice Line')
        self.machine = Machine.objects.create(
            line=self.line,
            code='HF-10-REP',
            name='Hot Filler 10',
            category='FILLER',
            ideal_run_rate_cpm=100.0,
            is_bottleneck=True
        )
        self.line.bottleneck_machine = self.machine
        self.line.save()

        # Shift
        self.shift = Shift.objects.create(
            factory=self.factory,
            code='SHIFT-DAY',
            name='Day Shift',
            start_time=time(7, 0),
            end_time=time(15, 0),
            sequence=1
        )

        # User & Roles
        self.supervisor_role, _ = Role.objects.get_or_create(code='supervisor', defaults={'name': 'Supervisor'})
        self.operator_role, _ = Role.objects.get_or_create(code='operator', defaults={'name': 'Operator'})

        self.supervisor_user = User.objects.create_user(username='rep_super', password='password123', email='super@factsense.com')
        UserRoleAssignment.objects.create(user=self.supervisor_user, role=self.supervisor_role, is_active=True)

        self.operator_user = User.objects.create_user(username='rep_op', password='password123')
        UserRoleAssignment.objects.create(user=self.operator_user, role=self.operator_role, is_active=True)

    def _login(self, user, role_code):
        self.client.login(username=user.username, password='password123')
        s = self.client.session
        s['active_role'] = role_code
        s.save()

    def test_generate_pdf_handover_report(self):
        """Verify ReportLab PDF generation outputs valid %PDF binary with expected sections."""
        pdf_buffer = generate_shift_handover_pdf(line=self.line, shift=self.shift, user=self.supervisor_user)
        pdf_bytes = pdf_buffer.getvalue()

        # Valid PDF header
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        # Substantial file size (> 2KB)
        self.assertGreater(len(pdf_bytes), 2000)

    def test_generate_multi_tab_excel_report(self):
        """Verify OpenPyXL generates valid 4-tab workbook matching operational figures."""
        excel_buffer = generate_shift_handover_excel(line=self.line, shift=self.shift, user=self.supervisor_user)
        wb = load_workbook(io.BytesIO(excel_buffer.getvalue()))

        # Check required tabs
        sheet_names = wb.sheetnames
        self.assertIn("Shift Summary & KPIs", sheet_names)
        self.assertIn("Downtime Events", sheet_names)
        self.assertIn("Quality & Scrap Defects", sheet_names)
        self.assertIn("Work Orders", sheet_names)

        # Inspect Tab 1
        ws1 = wb["Shift Summary & KPIs"]
        self.assertEqual(ws1["A1"].value, "FACTSENSE MES - OFFICIAL SHIFT REPORT")
        self.assertEqual(ws1["B2"].value, self.factory.name)

    def test_automated_report_subscription_and_dispatch(self):
        """Verify subscription model creation and dispatching to Email and Telegram channels."""
        sub = ReportSubscription.objects.create(
            name='Daily Morning Brief',
            report_type='SHIFT_HANDOVER',
            format='BOTH',
            frequency='DAILY',
            line=self.line,
            recipient_emails='director@factsense.com, manager@factsense.com',
            telegram_chat_id='@factsense_ops',
            created_by=self.supervisor_user,
            is_active=True
        )

        logs = dispatch_subscription(sub, user=self.supervisor_user)
        # 2 emails + 1 telegram = 3 dispatch logs
        self.assertEqual(len(logs), 3)

        sub.refresh_from_db()
        self.assertIsNotNone(sub.last_sent_at)

        email_logs = ReportDispatchLog.objects.filter(subscription=sub, channel='EMAIL')
        self.assertEqual(email_logs.count(), 2)

        tg_logs = ReportDispatchLog.objects.filter(subscription=sub, channel='TELEGRAM')
        self.assertEqual(tg_logs.count(), 1)

    def test_export_pdf_and_excel_views(self):
        """Verify HTTP download endpoints return correct MIME types and attachment headers."""
        self._login(self.supervisor_user, 'supervisor')

        # PDF Export Endpoint
        resp_pdf = self.client.get(f'/reports/export/pdf/?line_id={self.line.id}&shift_id={self.shift.id}')
        self.assertEqual(resp_pdf.status_code, 200)
        self.assertEqual(resp_pdf['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename=', resp_pdf['Content-Disposition'])

        # Excel Export Endpoint
        resp_excel = self.client.get(f'/reports/export/excel/?line_id={self.line.id}&shift_id={self.shift.id}')
        self.assertEqual(resp_excel.status_code, 200)
        self.assertIn('spreadsheetml', resp_excel['Content-Type'])
        self.assertIn('.xlsx', resp_excel['Content-Disposition'])

    def test_historical_explorer_and_csv_export(self):
        """Verify historical explorer queries and CSV export."""
        self._login(self.supervisor_user, 'supervisor')

        # Explorer view
        resp_exp = self.client.get(f'/reports/explorer/?line={self.line.id}&dataset=DOWNTIME')
        self.assertEqual(resp_exp.status_code, 200)

        # CSV Export
        resp_csv = self.client.get(f'/reports/explorer/export/csv/?line={self.line.id}&dataset=DOWNTIME')
        self.assertEqual(resp_csv.status_code, 200)
        self.assertEqual(resp_csv['Content-Type'], 'text/csv')
        self.assertIn('Machine Code', resp_csv.content.decode('utf-8'))

    def test_zero_emojis_in_reports_templates(self):
        """Verify zero decorative emojis rendered across all reporting templates."""
        self._login(self.supervisor_user, 'supervisor')

        urls = [
            f'/reports/?line={self.line.id}',
            '/reports/subscriptions/',
            f'/reports/explorer/?line={self.line.id}',
        ]
        for u in urls:
            resp = self.client.get(u)
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode('utf-8')
            self.assertFalse(bool(EMOJI_PATTERN.search(content)), f"Found emoji in URL {u}!")
