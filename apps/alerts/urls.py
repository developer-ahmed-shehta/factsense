from django.urls import path
from apps.alerts import views

urlpatterns = [
    path('', views.alerts_hub_view, name='alerts_home'),
    path('<uuid:alert_id>/acknowledge/', views.alert_acknowledge_action, name='alert_acknowledge_action'),
    path('<uuid:alert_id>/resolve/', views.alert_resolve_action, name='alert_resolve_action'),
    path('<uuid:alert_id>/escalate/', views.alert_escalate_action, name='alert_escalate_action'),
    path('rules/create/', views.alert_create_rule_action, name='alert_create_rule_action'),
    path('evaluate/', views.alert_evaluate_now_action, name='alert_evaluate_now_action'),
    path('api/drawer/', views.alert_drawer_api, name='alert_drawer_api'),
    path('api/count/', views.alert_unread_count_api, name='alert_unread_count_api'),
]

