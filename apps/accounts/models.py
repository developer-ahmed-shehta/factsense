import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Custom user model supporting Arabic names, language preferences,
    multi-role personas, and kiosk identifiers.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    arabic_name = models.CharField(max_length=150, blank=True, help_text="Arabic display name")
    preferred_language = models.CharField(
        max_length=10,
        default='en',
        choices=[('en', 'English'), ('ar', 'العربية')],
        help_text="Preferred interface language"
    )
    theme = models.CharField(
        max_length=20,
        default='light',
        choices=[('light', 'Light'), ('dark', 'Dark')],
        help_text="UI theme preference"
    )
    badge_number = models.CharField(max_length=50, blank=True, help_text="Shop-floor RFID badge or employee number")

    def __str__(self):
        display = self.get_full_name() or self.username
        if self.arabic_name:
            return f"{display} ({self.arabic_name})"
        return display

    def get_display_name(self, lang='en'):
        if lang == 'ar' and self.arabic_name:
            return self.arabic_name
        return self.get_full_name() or self.username

    def get_active_assignments(self):
        return self.role_assignments.filter(is_active=True).select_related('role', 'factory', 'line', 'machine')

    def get_roles(self):
        return [assignment.role for assignment in self.get_active_assignments()]

    def has_role(self, role_code):
        return self.role_assignments.filter(is_active=True, role__code=role_code).exists()


class Role(models.Model):
    """
    Canonical system role defining access boundaries and landing pages.
    """
    code = models.CharField(max_length=50, unique=True, help_text="Canonical role slug")
    name = models.CharField(max_length=100, help_text="English title")
    name_ar = models.CharField(max_length=100, help_text="Arabic title")
    default_landing = models.CharField(max_length=100, help_text="Default URL landing path")
    description = models.TextField(blank=True)
    sequence = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sequence', 'code']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_title(self, lang='en'):
        return self.name_ar if lang == 'ar' and self.name_ar else self.name


class UserRoleAssignment(models.Model):
    """
    User-to-Role assignment with hierarchical plant scope (factory, line, machine).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='role_assignments')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='assignments')
    factory = models.ForeignKey('masterdata.Factory', on_delete=models.CASCADE, null=True, blank=True, related_name='role_assignments')
    line = models.ForeignKey('masterdata.Line', on_delete=models.CASCADE, null=True, blank=True, related_name='role_assignments')
    machine = models.ForeignKey('masterdata.Machine', on_delete=models.CASCADE, null=True, blank=True, related_name='role_assignments')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "User Role Assignment"
        verbose_name_plural = "User Role Assignments"

    def __str__(self):
        scope_parts = []
        if self.factory:
            scope_parts.append(f"Plant: {self.factory.code}")
        if self.line:
            scope_parts.append(f"Line: {self.line.code}")
        if self.machine:
            scope_parts.append(f"Mach: {self.machine.code}")
        scope_str = " | ".join(scope_parts) if scope_parts else "Global Scope"
        return f"{self.user.username} -> {self.role.code} ({scope_str})"


class DeviceEnrollment(models.Model):
    """
    Enrolled shop-floor kiosk hardware token paired to physical equipment.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device_token = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    machine = models.ForeignKey('masterdata.Machine', on_delete=models.CASCADE, null=True, blank=True, related_name='devices')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Kiosk {self.name} -> {self.machine}"


class OperatorSession(models.Model):
    """
    Tracks active shop-floor kiosk session ensuring one-operator-per-machine exclusivity.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kiosk_sessions')
    machine = models.ForeignKey('masterdata.Machine', on_delete=models.CASCADE, related_name='operator_sessions')
    session_key = models.CharField(max_length=100)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Session: {self.operator.username} @ {self.machine.code} (Active: {self.is_active})"


class AuditEvent(models.Model):
    """
    Audit trail recording actor, active role persona, scope, action, and details.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_events')
    active_role = models.CharField(max_length=50, blank=True)
    action = models.CharField(max_length=100)
    resource = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=100, blank=True)
    scope_factory = models.CharField(max_length=100, blank=True)
    scope_line = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        actor_name = self.actor.username if self.actor else "System"
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {actor_name} ({self.active_role}): {self.action} on {self.resource}"
