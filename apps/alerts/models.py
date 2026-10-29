"""
Real-Time Alerts, Alarm Storm Engine & Deduplication Models.
Strictly implements:
- F08: Configurable Alert Rules (Downtime duration, low speed, defect spikes, weight out-of-spec, vibration, temperature)
- Alarm Storm Deduplication & Cooldown Suppression Window
- Auto-Resolve Watchdog tracking telemetry recovery conditions
- Full Alert Lifecycle: ACTIVE -> ACKNOWLEDGED -> RESOLVED
- Direct escalation to formal MaintenanceTicket
- Global Notification Drawer integration
"""

import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.masterdata.models import Factory, Line, Machine
from apps.operations.models import MaintenanceTicket


RULE_SCOPE_CHOICES = [
    ('GLOBAL', 'Global (All Lines & Machines)'),
    ('LINE', 'Line Specific'),
    ('MACHINE', 'Machine Specific'),
]

RULE_TYPE_CHOICES = [
    ('DOWNTIME_DURATION', 'Continuous Downtime Duration Exceeded'),
    ('LOW_SPEED', 'Low Operating Speed / Speed Loss'),
    ('DEFECT_SPIKE', 'Defect / Scrap Rate Spike'),
    ('WEIGHT_OUT_OF_SPEC', 'Consecutive Weight Out of Specification'),
    ('TEMPERATURE_HIGH', 'Machine Temperature Overheat'),
    ('VIBRATION_HIGH', 'Excessive Vibration RMS'),
]

SEVERITY_CHOICES = [
    ('INFO', 'Informational'),
    ('WARNING', 'Warning'),
    ('CRITICAL', 'Critical Alert'),
]

ALERT_STATUS_CHOICES = [
    ('ACTIVE', 'Active (Unacknowledged)'),
    ('ACKNOWLEDGED', 'Acknowledged'),
    ('RESOLVED', 'Resolved'),
]


class AlertRule(models.Model):
    """
    Configurable industrial alert trigger rule with cooldown suppression window.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    name_ar = models.CharField(max_length=150, blank=True)
    scope = models.CharField(max_length=20, choices=RULE_SCOPE_CHOICES, default='GLOBAL')
    
    factory = models.ForeignKey(Factory, on_delete=models.CASCADE, null=True, blank=True, related_name='alert_rules')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, null=True, blank=True, related_name='alert_rules')
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, null=True, blank=True, related_name='alert_rules')
    
    rule_type = models.CharField(max_length=40, choices=RULE_TYPE_CHOICES, default='DOWNTIME_DURATION')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='WARNING')
    
    threshold_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'),
                                          help_text="Threshold value (e.g. minutes for downtime, % for scrap, °C for temp)")
    duration_seconds = models.PositiveIntegerField(default=300,
                                                   help_text="Time condition must persist before trigger (seconds)")
    cooldown_minutes = models.PositiveIntegerField(default=10,
                                                   help_text="Cooldown suppression window in minutes to prevent alarm storms.")
    
    auto_resolve = models.BooleanField(default=True,
                                       help_text="Automatically resolve alert when telemetry recovers to normal parameters.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['severity', 'name']
        verbose_name = 'Alert Rule'
        verbose_name_plural = 'Alert Rules'

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.name} ({self.get_rule_type_display()})"


class AlertIncident(models.Model):
    """
    Active or historical industrial alert event.
    Implements deduplication counters and direct maintenance ticket escalation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(AlertRule, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='alert_incidents')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='alert_incidents')
    
    rule_type = models.CharField(max_length=40, choices=RULE_TYPE_CHOICES, default='DOWNTIME_DURATION')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='WARNING')
    
    title = models.CharField(max_length=200)
    title_ar = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    message_ar = models.TextField(blank=True)
    
    status = models.CharField(max_length=20, choices=ALERT_STATUS_CHOICES, default='ACTIVE', db_index=True)
    
    # Alarm Storm Deduplication: increments when identical fault recurs during cooldown
    occurrences_count = models.PositiveIntegerField(default=1,
                                                    help_text="Number of deduplicated triggers suppressed into this single incident.")
    
    first_triggered_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_triggered_at = models.DateTimeField(default=timezone.now)
    
    # Acknowledgement
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='acknowledged_alerts')
    
    # Resolution
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='resolved_alerts')
    resolution_note = models.TextField(blank=True)
    
    # Direct escalation to formal Maintenance Kanban ticket
    spawned_ticket = models.ForeignKey(MaintenanceTicket, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='escalated_alerts')
    
    is_simulated = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-first_triggered_at']
        verbose_name = 'Alert Incident'
        verbose_name_plural = 'Alert Incidents'

    def __str__(self):
        return f"[{self.severity}] {self.machine.code}: {self.title} ({self.status}, x{self.occurrences_count})"

    @property
    def duration_open_minutes(self):
        end = self.resolved_at or timezone.now()
        return max(1, int((end - self.first_triggered_at).total_seconds() / 60))


class AlertSuppressionLog(models.Model):
    """
    Audit log of deduplicated/suppressed alarms during alarm storm events.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(AlertIncident, on_delete=models.CASCADE, related_name='suppression_logs')
    rule = models.ForeignKey(AlertRule, on_delete=models.SET_NULL, null=True, blank=True)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    suppressed_at = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=200, default='Suppression window active (cooldown)')

    class Meta:
        ordering = ['-suppressed_at']

