"""
Root URL Configuration for FactSense MES.
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from apps.accounts import views as account_views

urlpatterns = [
    # Root entrypoint
    path('', account_views.role_landing_view, name='root'),
    
    # Django Admin
    path('django-admin/', admin.site.urls),

    # Authentication & Accounts
    path('accounts/', include('apps.accounts.urls')),
    path('login/', account_views.login_view, name='login_direct'),
    path('logout/', account_views.logout_view, name='logout_direct'),

    # Master Data & Products (Matching Section 2.4 reference)
    path('masterdata/', include('apps.masterdata.urls')),
    path('planning/', include('apps.masterdata.urls')),  # Alias /planning/products/ to masterdata

    # Telemetry Ingestion & Industrial Calculation APIs
    path('api/v1/', include('apps.telemetry.urls')),
    path('api/', include('apps.telemetry.urls')),

    # Operations & Maintenance Actions
    path('', include('apps.operations.urls')),

    # Quality & SPC Hub
    path('quality/', include('apps.quality.urls')),

    # Real-Time Alerts & Alarm Storm Engine
    path('alerts/', include('apps.alerts.urls')),

    # Planning, Work Orders & ERP Sync
    path('work-orders/', include('apps.planning.urls')),

    # Industrial AI Copilot (Dual-Engine)
    path('copilot/', include('apps.copilot.urls')),

    # Shift Handover & Production Reports
    path('reports/', include('apps.reports.urls')),

    # Portal Modules & Role Homes
    path('', include('apps.portal.urls')),
]
