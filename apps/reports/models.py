"""
Models for Shift Handover & Production Reporting, Automated Subscriptions,
and Dispatch Logs.
Fulfills F10 and Batch 7 specifications.
"""

import uuid
from django.db import models
from django.conf import settings
from apps.masterdata.models import Line


class ReportSubscription(models.Model):
    """
    Automated scheduled report distribution subscription via Email and Telegram.
    """
    REPORT_TYPE_CHOICES = [
        ('SHIFT_HANDOVER', 'Shift Handover Executive Summary'),
        ('DAILY_OEE', 'Daily Line OEE & Loss Waterfall'),
        ('QUALITY_SPC', 'Quality SPC & Weight Giveaway Analysis'),
        ('DOWNTIME_PARETO', 'Equipment Reliability & Downtime Pareto'),
    ]

    FORMAT_CHOICES = [
        ('PDF', 'Printable PDF Document'),
        ('EXCEL', 'Structured Excel Workbook (.xlsx)'),
        ('BOTH', 'Both PDF and Excel (.xlsx)'),
    ]

    FREQUENCY_CHOICES = [
        ('END_OF_SHIFT', 'At End of Every Shift Window'),
        ('DAILY', 'Daily Morning Digest (07:00)'),
        ('WEEKLY', 'Weekly Operations Review (Sunday 08:00)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES, default='SHIFT_HANDOVER')
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES, default='PDF')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='END_OF_SHIFT')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='report_subscriptions')
    recipient_emails = models.CharField(max_length=500, blank=True, help_text='Comma-separated email recipients')
    telegram_chat_id = models.CharField(max_length=100, blank=True, help_text='Telegram channel or user chat ID')
    is_active = models.BooleanField(default=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} [{self.get_report_type_display()}] ({self.frequency})"


class ReportDispatchLog(models.Model):
    """
    Audit log of dispatched automated or manual reports.
    """
    CHANNEL_CHOICES = [
        ('EMAIL', 'Email Distribution'),
        ('TELEGRAM', 'Telegram Bot'),
        ('MANUAL_DOWNLOAD', 'Direct Manual Download'),
    ]

    STATUS_CHOICES = [
        ('SENT', 'Successfully Dispatched'),
        ('FAILED', 'Dispatch Failed'),
        ('SIMULATED', 'Simulated Dispatch (Development/Testing)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        ReportSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dispatch_logs'
    )
    report_type = models.CharField(max_length=50)
    format = models.CharField(max_length=20)
    recipient = models.CharField(max_length=255)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='EMAIL')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SENT')
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.report_type} ({self.format}) to {self.recipient} via {self.channel}: {self.status}"
