from django.urls import path
from . import views

urlpatterns = [
    # Work Order Central Dispatch
    path('', views.work_orders_dispatch_view, name='work_orders_home'),
    path('create/', views.work_order_create_view, name='work_order_create'),
    path('<uuid:order_id>/', views.work_order_detail_view, name='work_order_detail'),
    path('<uuid:order_id>/action/', views.work_order_action_view, name='work_order_action'),

    # Shift Assignment Matrix
    path('schedule/', views.work_orders_schedule_matrix_view, name='work_orders_schedule'),
    path('schedule/assign/', views.work_order_assign_shift_view, name='work_order_assign_shift'),

    # Material Staging Checklist
    path('materials/', views.work_orders_materials_view, name='work_orders_materials'),
    path('materials/<uuid:material_id>/stage/', views.work_order_material_stage_action, name='work_order_material_stage'),
    path('materials/<uuid:material_id>/shortage/', views.work_order_material_shortage_action, name='work_order_material_shortage'),

    # ERP / Odoo Synchronization & Conflict Queue
    path('erp-sync/', views.work_orders_erp_sync_view, name='work_orders_erp_sync'),
    path('erp-sync/trigger/', views.work_orders_erp_trigger_sync, name='work_orders_erp_trigger_sync'),
    path('erp-sync/resolve/<uuid:conflict_id>/', views.work_orders_erp_resolve_conflict, name='work_orders_erp_resolve_conflict'),
    path('erp-sync/retry/<uuid:run_id>/', views.work_orders_erp_retry, name='work_orders_erp_retry'),
]

