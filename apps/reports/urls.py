from django.urls import path
from . import views

urlpatterns = [
    # Reports Hub
    path('', views.reports_home_view, name='reports_home'),
    path('export/pdf/', views.export_pdf_view, name='reports_export_pdf'),
    path('export/excel/', views.export_excel_view, name='reports_export_excel'),

    # Subscriptions & Distribution
    path('subscriptions/', views.subscriptions_view, name='reports_subscriptions'),
    path('subscriptions/create/', views.subscription_create_view, name='reports_subscription_create'),
    path('subscriptions/<uuid:sub_id>/dispatch/', views.subscription_dispatch_now_view, name='reports_subscription_dispatch'),

    # Historical Data Explorer
    path('explorer/', views.historical_explorer_view, name='reports_explorer'),
    path('explorer/export/csv/', views.historical_export_csv_view, name='reports_explorer_export_csv'),
]

