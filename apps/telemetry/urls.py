"""
URL configuration for FactSense Telemetry & Industrial Calculation APIs.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Telemetry Ingestion & Live Streams (F02, F13)
    path('telemetry/ingest/', views.telemetry_ingest_api, name='api_telemetry_ingest'),
    path('telemetry/live/<str:line_code>/', views.telemetry_live_api, name='api_telemetry_live'),
    path('telemetry/stream/<str:line_code>/', views.telemetry_stream_api, name='api_telemetry_stream'),

    # Industrial Calculation REST APIs (F03, F13)
    path('calculation/line/<str:line_code>/kpi/', views.line_kpi_api, name='api_line_kpi'),
    path('calculation/line/<str:line_code>/waterfall/', views.line_waterfall_api, name='api_line_waterfall'),
    path('calculation/line/<str:line_code>/hourly/', views.line_hourly_api, name='api_line_hourly'),

    # Controller Actions (F12)
    path('controller/scenario/', views.controller_scenario_apply, name='controller_scenario_apply'),
    path('controller/clock/', views.controller_clock_apply, name='controller_clock_apply'),
    path('controller/step/', views.controller_step_action, name='controller_step_action'),
    path('controller/reset/', views.controller_reset_action, name='controller_reset_action'),
    path('controller/override/', views.controller_override_machine, name='controller_override_machine'),
]

