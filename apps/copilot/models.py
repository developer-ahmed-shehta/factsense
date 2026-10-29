"""
Models for FactSense Industrial AI Copilot (Dual-Engine: Cloud Gemini + Edge Fallback).
Fulfills F09 and Batch 7 specifications.
"""

import uuid
from django.db import models
from django.conf import settings
from apps.masterdata.models import Line


class CopilotChatSession(models.Model):
    """
    Persistent conversational session for industrial AI copilot queries.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='copilot_sessions'
    )
    title = models.CharField(max_length=150, default='Industrial Chat')
    line = models.ForeignKey(Line, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.title} ({self.user.username})"


class CopilotChatMessage(models.Model):
    """
    Individual turn within a Copilot session, tracking user query or AI response,
    engine attribution, and interactive action chips.
    """
    ROLE_CHOICES = [
        ('user', 'User Query'),
        ('assistant', 'Copilot Assistant'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        CopilotChatSession,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    action_chips = models.JSONField(default=list, blank=True)
    engine_used = models.CharField(max_length=100, default='Offline Heuristic Engine (Edge Fallback)')
    context_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.role}] {self.content[:40]}..."

