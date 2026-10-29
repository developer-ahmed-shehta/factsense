"""
URL Configuration for FactSense Shop-Floor Operations, Maintenance & Operator Console.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Operator HMI Actions (F05)
    path('operator/increment/', views.operator_increment_count_action, name='operator_increment_action'),
    path('operator/classify/', views.operator_classify_action, name='operator_classify_action'),
    path('operator/split/', views.operator_split_action, name='operator_split_action'),
    path('operator/scrap/', views.operator_scrap_action, name='operator_scrap_action'),
    path('operator/weight/', views.operator_weight_action, name='operator_weight_action'),
    path('operator/call-maintenance/', views.operator_call_maintenance_action, name='operator_call_maintenance_action'),
    path('operator/cancel-call/', views.operator_cancel_call_action, name='operator_cancel_call_action'),
    path('operator/session/release/', views.operator_session_release_action, name='operator_session_release_action'),
    path('operator/session/override/', views.operator_session_override_action, name='operator_session_override_action'),

    # SMED Actions (F06)
    path('smed/start/', views.smed_start_action, name='smed_start_action'),
    path('smed/next-phase/', views.smed_next_phase_action, name='smed_next_phase_action'),

    # Maintenance Actions (F16)
    path('maintenance/clock-in/', views.maintenance_clock_in_action, name='maintenance_clock_in_action'),
    path('maintenance/request-spare/', views.maintenance_request_spare_action, name='maintenance_request_spare_action'),
    path('maintenance/deliver-spare/', views.maintenance_deliver_spare_action, name='maintenance_deliver_spare_action'),
    path('maintenance/resolve/', views.maintenance_resolve_action, name='maintenance_resolve_action'),

    # Shift Handover Actions (F15)
    path('shifts/handover/submit/', views.shift_handover_submit_action, name='shift_handover_submit_action'),
]

