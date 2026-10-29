from django.urls import path
from . import views

urlpatterns = [
    # Reference Product Management (Section 2.4)
    path('products/', views.products_list_view, name='products_list'),
    path('products/add/', views.product_add_view, name='product_add'),
    path('products/<uuid:product_id>/edit/', views.product_edit_view, name='product_edit'),
    path('products/<uuid:product_id>/archive/', views.product_archive_view, name='product_archive'),

    # 60-Second Onboarding Wizard & Presets (F11)
    path('wizard/', views.wizard_view, name='wizard'),

    # Interactive Factory Topology Hub (F11)
    path('topology/', views.topology_view, name='topology'),

    # Machine Asset Setup (F01)
    path('machines/', views.machines_list_view, name='machines_list'),
    path('machines/add/', views.machine_add_view, name='machine_add'),
    path('machines/<uuid:machine_id>/edit/', views.machine_edit_view, name='machine_edit'),

    # MachineProductRate Speed Matrix (F01)
    path('rates/', views.rates_matrix_view, name='rates_matrix'),
    path('rates/update/', views.rate_update_view, name='rate_update'),

    # Shifts, Schedules & Planned Breaks (F01)
    path('shifts/', views.shifts_list_view, name='shifts_list'),
    path('shifts/add/', views.shift_add_view, name='shift_add'),
    path('shifts/breaks/add/', views.break_add_view, name='break_add'),

    # Stoppage & Defect Taxonomies (F01)
    path('reasons/', views.reasons_taxonomies_view, name='reasons_taxonomies'),
    path('reasons/add/', views.reason_add_view, name='reason_add'),
    path('reasons/defects/add/', views.defect_add_view, name='defect_add'),

    # Process Catalog (F01)
    path('processes/', views.processes_list_view, name='processes_list'),
    path('processes/add/', views.process_add_view, name='process_add'),

    # Hardware Kiosks & Gateway Onboarding (F11, F19)
    path('kiosk-pairing/', views.kiosk_pairing_view, name='kiosk_pairing'),
    path('kiosk-pairing/claim/', views.claim_kiosk_view, name='claim_kiosk'),
]
