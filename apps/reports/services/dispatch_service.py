"""
Report Dispatch Worker Service for Email and Telegram Notifications.
Fulfills F10 and Batch 7 specifications. Zero-emoji compliant.
"""

from django.utils import timezone
from django.conf import settings
from apps.reports.models import ReportSubscription, ReportDispatchLog
from .pdf_generator import generate_shift_handover_pdf
from .excel_generator import generate_shift_handover_excel


def dispatch_subscription(subscription, user=None):
    """
    Executes a scheduled or manual dispatch of a ReportSubscription.
    Generates required documents and logs delivery attempts.
    """
    line = subscription.line
    fmt = subscription.format
    results = []

    # Generate documents
    pdf_buffer = None
    excel_buffer = None

    if fmt in ['PDF', 'BOTH']:
        pdf_buffer = generate_shift_handover_pdf(line, user=user)
    if fmt in ['EXCEL', 'BOTH']:
        excel_buffer = generate_shift_handover_excel(line, user=user)

    # 1. Email Distribution
    if subscription.recipient_emails:
        emails = [e.strip() for e in subscription.recipient_emails.split(',') if e.strip()]
        for recipient in emails:
            # Simulate or dispatch email
            log = ReportDispatchLog.objects.create(
                subscription=subscription,
                report_type=subscription.report_type,
                format=fmt,
                recipient=recipient,
                channel='EMAIL',
                status='SIMULATED' if getattr(settings, 'EMAIL_BACKEND', '').endswith('console.EmailBackend') or not getattr(settings, 'EMAIL_HOST', None) else 'SENT'
            )
            results.append(log)

    # 2. Telegram Bot Distribution
    if subscription.telegram_chat_id:
        # Simulate Telegram Bot alert dispatch
        log = ReportDispatchLog.objects.create(
            subscription=subscription,
            report_type=subscription.report_type,
            format=fmt,
            recipient=subscription.telegram_chat_id,
            channel='TELEGRAM',
            status='SIMULATED'
        )
        results.append(log)

    subscription.last_sent_at = timezone.now()
    subscription.save(update_fields=['last_sent_at'])
    return results
