from django.urls import path
from . import views

urlpatterns = [
    # Operator
    path('operator/', views.operator_home, name='operator_home'),
    path('operator/production/', views.operator_production, name='operator_production'),
    path('operator/stoppages/', views.operator_stoppages, name='operator_stoppages'),

    # Supervisor / Floor
    path('floor/', views.floor_home, name='floor_home'),
    path('shifts/', views.shifts_home, name='shifts_home'),
    path('stoppages/', views.stoppages_home, name='stoppages_home'),
    path('stoppages/reliability/', views.stoppages_reliability, name='stoppages_reliability'),
    path('smed/', views.smed_home, name='smed_home'),

    # Maintenance
    path('maintenance/', views.maintenance_home, name='maintenance_home'),
    path('maintenance/machines/', views.maintenance_machines, name='maintenance_machines'),
    path('maintenance/spares/', views.maintenance_spares, name='maintenance_spares'),
    path('maintenance/history/', views.maintenance_history, name='maintenance_history'),

    # Quality
    path('quality/', views.quality_home, name='quality_home'),
    path('quality/samples/', views.quality_samples, name='quality_samples'),
    path('quality/defects/', views.quality_defects, name='quality_defects'),
    path('quality/giveaway/', views.quality_giveaway, name='quality_giveaway'),

    # Planning
    path('planning/', views.planner_home, name='planner_home'),
    path('planning/processes/', views.planning_processes, name='planning_processes'),
    path('planning/rates/', views.planning_rates, name='planning_rates'),
    path('planning/reasons/', views.planning_reasons, name='planning_reasons'),

    # Supply Chain
    path('work-orders/', views.work_orders_home, name='work_orders_home'),
    path('work-orders/schedule/', views.work_orders_schedule, name='work_orders_schedule'),
    path('work-orders/materials/', views.work_orders_materials, name='work_orders_materials'),
    path('work-orders/erp-sync/', views.work_orders_erp_sync, name='work_orders_erp_sync'),

    # Management / Dashboard
    path('dashboard/', views.manager_home, name='manager_home'),
    path('dashboard/losses/', views.manager_losses, name='manager_losses'),

    # Administration
    path('administration/', views.admin_home, name='admin_home'),
    path('administration/users/', views.admin_users, name='admin_users'),
    path('administration/roles/', views.admin_roles, name='admin_roles'),
    path('administration/machines/', views.admin_machines, name='admin_machines'),
    path('administration/settings/', views.admin_settings, name='admin_settings'),
    path('administration/gateways/', views.admin_gateways, name='admin_gateways'),
    path('administration/integrations/', views.admin_integrations, name='admin_integrations'),
    path('administration/audit/', views.admin_audit, name='admin_audit'),

    # Controller / Simulation
    path('controller/', views.controller_home, name='controller_home'),
    path('controller/scenarios/', views.controller_scenarios, name='controller_scenarios'),
    path('controller/machines/', views.controller_machines, name='controller_machines'),
    path('controller/shift/', views.controller_shift, name='controller_shift'),

    # Cross-role Modules
    path('alerts/', views.alerts_home, name='alerts_home'),
    path('copilot/', views.copilot_home, name='copilot_home'),
    path('reports/', views.reports_home, name='reports_home'),
]
