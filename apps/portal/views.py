"""
Role-specific landing pages and module routers.
Enforces strict server-side role permissions and clear batch labeling.
"""

from django.shortcuts import render, redirect
from apps.accounts.decorators import role_required
from apps.masterdata.models import Product, Machine, Line, Factory


# ==============================================================================
# Canonical Role Homes (Batch 1 Scope)
# ==============================================================================

@role_required('operator', 'admin')
def operator_home(request):
    """
    Operator Touch Console landing (/operator/).
    """
    return render(request, 'portal/operator_home.html', {
        'page_title': 'Operator Machine Console',
        'page_title_ar': 'لوحة تحكم مشغل الماكينة',
        'batch_id': 'Batch 4',
        'scheduled_features': [
            '10"–15" Glove-friendly touch ergonomic interface (48px+ touch targets)',
            'Large digital good piece counter with +1, +5, +10 quick touch increments',
            'Defect and scrap counter with rapid categorization keypad',
            'Prominent equipment state banner (RUNNING, DOWNTIME, BLOCKED, STARVED)',
            '2-Level Stoppage classification and stop-splitting modal',
            'Maintenance call button and changeover initiator',
            'Kiosk session exclusivity (one operator per machine)',
        ]
    })


@role_required('supervisor', 'maintenance', 'quality', 'planner', 'supply_chain', 'manager', 'admin')
def floor_home(request):
    """
    Supervisor Live Floor Hub landing (/floor/).
    """
    return render(request, 'portal/supervisor_home.html', {
        'page_title': 'Shop Floor Live Overview',
        'page_title_ar': 'نظرة عامة حية لصالة الإنتاج',
        'batch_id': 'Batch 4',
        'scheduled_features': [
            'Visual 20-machine factory matrix with real-time state color borders',
            'Active work order progress and pacing against shift quota',
            'Bottleneck machine constraint identification',
            'Shift progress strip with Availability, Performance, and Quality gauges',
            'Quick maintenance technician dispatch',
            'Guided 3-step shift handover wizard',
        ]
    })


@role_required('maintenance', 'supervisor', 'admin')
def maintenance_home(request):
    """
    Maintenance Operations Center landing (/maintenance/).
    """
    return render(request, 'portal/maintenance_home.html', {
        'page_title': 'Maintenance Operations Center',
        'page_title_ar': 'مركز عمليات الصيانة وإدارة الأعطال',
        'batch_id': 'Batch 4',
        'scheduled_features': [
            '5-Stage Kanban Incident Board (Open -> Assigned -> In Progress -> Waiting Spares -> Resolved)',
            'Mobile-friendly technician repair clock-in sheet',
            'Spare parts requisition with SLA timer pausing',
            'Mandatory root cause and solution logging before machine release',
            'Machine force-lockout workflow and release to production',
        ]
    })



@role_required('quality', 'supervisor', 'manager', 'admin')
def quality_home(request):
    """
    Quality & Weight Giveaway SPC landing (/quality/).
    """
    return render(request, 'portal/quality_home.html', {
        'page_title': 'Quality Assurance & SPC Control Hub',
        'page_title_ar': 'إدارة الجودة والتحكم الإحصائي في العمليات (SPC)',
        'batch_id': 'Batch 5',
        'scheduled_features': [
            'ISO 22400-2 Statistical Process Control (X-bar and R charts with UCL/LCL/CL)',
            'Gaussian Normal Distribution bell curve with process mean and standard deviation',
            'Process capability metrics (Cp and Cpk centering indices)',
            'Overfill product giveaway financial cost calculator',
            'Interactive recalibration slider showing raw material savings with zero underfill risk',
            'Raw weight sample exports to CSV/Excel',
        ]
    })


@role_required('planner', 'admin', 'manager')
def planner_home(request):
    """
    Production Planner Home landing (/planning/).
    Directs to Product Management as the primary planning master view.
    """
    return redirect('products_list')


@role_required('supply_chain', 'planner', 'manager', 'admin')
def work_orders_home(request):
    """
    Supply Chain & Work Order Dispatch landing (/work-orders/).
    """
    return render(request, 'portal/supply_chain_home.html', {
        'page_title': 'Work Order Dispatch & Supply Chain',
        'page_title_ar': 'إدارة أوامر العمل وسلاسل الإمداد',
        'batch_id': 'Batch 6',
        'scheduled_features': [
            'Consolidated ERP / Odoo work order synchronization queue',
            'Visual machine assignment calendar across Morning, Evening, and Night shifts',
            'Bill of Operations & multi-stage process routing tracker',
            'Component material delivery and staged progress monitoring',
            'Work order short-close reconciliation workflow',
        ]
    })


@role_required('manager', 'admin')
def manager_home(request):
    """
    Executive Management Overview & Dashboard landing (/dashboard/).
    """
    return render(request, 'portal/manager_home.html', {
        'page_title': 'Executive OEE & Plant Command Center',
        'page_title_ar': 'لوحة القيادة التنفيذية ومؤشرات الفعالية الكلية (OEE)',
        'batch_id': 'Batch 5',
        'scheduled_features': [
            'Actionable "So What?" Executive Banner with active bottleneck and loss summary',
            'Line OEE benchmark gauges against World-Class 85.0% target (Availability, Performance, Quality)',
            'TPM Six Big Losses financial waterfall visualizer',
            'Shift progress pacing chart and hourly production run trend',
            'Live conveyor strip showing all line machines in physical sequence',
            'Financial downtime opportunity cost calculator',
        ]
    })


@role_required('admin')
def admin_home(request):
    """
    System Administration & Plant Topology landing (/administration/).
    """
    return render(request, 'portal/admin_home.html', {
        'page_title': 'System Administration & Plant Configuration',
        'page_title_ar': 'إدارة النظام والتهيئة المعمارية للمصنع',
        'batch_id': 'Batch 2 & 8',
        'scheduled_features': [
            'User provisioning, role assignments, and plant-level scoping',
            'Asset topology: Factories, Lines, and Machines hierarchy',
            'IoT Gateway QR code onboarding and hardware claim',
            'Shift definitions and planned break calendars',
            'Email and Telegram notification bot integration rules',
            'System audit logs and configuration diagnostics',
        ]
    })


@role_required('controller', 'admin')
def controller_home(request):
    """
    Simulator & Demo Controller landing (/controller/).
    """
    return render(request, 'portal/controller_home.html', {
        'page_title': 'Simulation Controller & Signal Generator',
        'page_title_ar': 'لوحة التحكم في المحاكاة ومولد الإشارات التجريبية',
        'batch_id': 'Batch 3',
        'scheduled_features': [
            'Synthetic telemetry pulse generator (CPM, vibration, temperature, states)',
            'Simulation clock multiplier (Paused, 1x, 2x, 5x, 10x speed)',
            '5 Pre-built scenario injectors: Cap Chute Jam, Overfill Giveaway Drift, Mechanical Breakdown, Defect Burst, Golden Run (95% OEE)',
            'Manual machine telemetry override sliders',
            'Shift transition trigger and isolated demo database reset',
            'Persistent "DEMO MODE ACTIVE" visual badge',
        ]
    })


# ==============================================================================
# Secondary Navigation Views (With Strict Role Security & Batch Labeling)
# ==============================================================================

def generic_module_view(request, title, title_ar, batch_id, features, allowed_roles):
    """Reusable helper for batch roadmap modules with strict permission check."""
    from apps.accounts.decorators import role_required
    
    @role_required(*allowed_roles)
    def view(req):
        return render(req, 'portal/module_placeholder.html', {
            'page_title': title,
            'page_title_ar': title_ar,
            'batch_id': batch_id,
            'scheduled_features': features,
            'allowed_roles': allowed_roles,
        })
    return view(request)


# Operator Secondary
@role_required('operator', 'admin')
def operator_production(request):
    return generic_module_view(request, 'Operator Production Entry', 'تسجيل كميات الإنتاج', 'Batch 4', [
        'Touch-based numeric scrap and good piece counter',
        'Current running work order and target speed',
    ], ['operator', 'admin'])

@role_required('operator', 'admin')
def operator_stoppages(request):
    return generic_module_view(request, 'Operator Stoppages & Classification', 'تصنيف التوقفات للمشغل', 'Batch 4', [
        'Active machine stoppage timer',
        'One-touch 2-level root cause categorization modal',
    ], ['operator', 'admin'])


# Supervisor Secondary
@role_required('supervisor', 'planner', 'admin')
def shifts_home(request):
    return generic_module_view(request, 'Shift Lifecycle & Schedules', 'إدارة الورديات وجداول العمل', 'Batch 2', [
        'Shift definition (Morning, Evening, Night) and planned breaks',
        'Active shift progress and elapsed operating time',
        'End-of-shift handover sign-off checklist',
    ], ['supervisor', 'planner', 'admin'])

@role_required('supervisor', 'maintenance', 'manager', 'admin')
def stoppages_home(request):
    return generic_module_view(request, 'Stoppage Registry & Downtime Intelligence', 'سجل التوقفات وتحليل زمن التعطل', 'Batch 4', [
        'Real-time active downtime event registry',
        'Juran 80/20 Pareto curve (By Duration vs By Frequency)',
        'Downtime event split and reclassification audit',
    ], ['supervisor', 'maintenance', 'manager', 'admin'])

@role_required('supervisor', 'manager', 'admin')
def smed_home(request):
    return generic_module_view(request, 'SMED Changeover Stopwatch', 'مؤقت تبديل القوالب والمنتجات (SMED)', 'Batch 4', [
        'Shigeo Shingo 4-Phase SMED changeover tracker',
        'Phase 1: Line Clearance & CIP Purge',
        'Phase 2: Mechanical Tooling Change',
        'Phase 3: Digital Recipe Loading',
        'Phase 4: Test Run & Speed Ramp-up Rejects',
    ], ['supervisor', 'manager', 'admin'])

@role_required('supervisor', 'maintenance', 'quality', 'planner', 'manager', 'admin')
def alerts_home(request):
    return generic_module_view(request, 'Real-Time Alerts & Alarm Storm Engine', 'مركز التنبيهات المباشرة وإدارة الإنذارات', 'Batch 5', [
        'Scoped alert rules (Downtime duration, low speed, defect spikes, vibration, temperature)',
        'Alarm storm suppression window and deduplication',
        'Auto-resolve watchdog returning alerts to normal when machine resumes',
        'Direct button to spawn formal Maintenance Ticket from alert',
    ], ['supervisor', 'maintenance', 'quality', 'planner', 'manager', 'admin'])

@role_required('supervisor', 'maintenance', 'quality', 'planner', 'manager', 'admin')
def copilot_home(request):
    return generic_module_view(request, 'FactSense Industrial AI Copilot', 'المساعد الذكي للمصنع (Dual-Engine AI)', 'Batch 7', [
        'Dual-Engine: Google Gemini Flash Cloud API + Offline Deterministic Heuristics',
        'Bilingual Natural Language Q&A in English and Arabic',
        'Context-aware database queries for OEE, bottlenecks, stops, and giveaway losses',
        'Interactive clickable action chips linking to machine consoles and Pareto charts',
    ], ['supervisor', 'maintenance', 'quality', 'planner', 'manager', 'admin'])

@role_required('supervisor', 'maintenance', 'quality', 'planner', 'supply_chain', 'manager', 'admin')
def reports_home(request):
    return generic_module_view(request, 'Shift Handover & Production Reports', 'تقارير تسليم الوردية والإنتاج', 'Batch 7', [
        'Official 4-bullet executive shift handover summary',
        'High-resolution PDF report export ready for print',
        'Multi-tab Excel (.xlsx) workbook export for data science',
        'Automated report subscriptions and email/Telegram distribution',
    ], ['supervisor', 'maintenance', 'quality', 'planner', 'supply_chain', 'manager', 'admin'])


# Maintenance Secondary
@role_required('maintenance', 'admin')
def maintenance_machines(request):
    return generic_module_view(request, 'Asset Health & Equipment Status', 'حالة الماكينات والأصول الصناعية', 'Batch 4', [
        'Machine maintenance telemetry (Vibration RMS, temperature)',
        'Equipment history, MTBF, and maintenance ticket logs',
    ], ['maintenance', 'admin'])

@role_required('maintenance', 'admin')
def maintenance_spares(request):
    return generic_module_view(request, 'Spare Parts Requests & Inventory', 'طلبات قطع الغيار ومخزون الصيانة', 'Batch 4', [
        'Spare parts requisition workflow',
        'Ticket pause on parts delay with SLA clock adjustment',
    ], ['maintenance', 'admin'])

@role_required('maintenance', 'admin')
def maintenance_history(request):
    return generic_module_view(request, 'Repair History & Root Cause Audit', 'سجل الإصلاحات والتحليل الجذري للأعطال', 'Batch 4', [
        'Historical maintenance tickets with verified solutions',
        'Technician clock-in/out timestamps and repair durations',
    ], ['maintenance', 'admin'])

@role_required('maintenance', 'supervisor', 'manager', 'admin')
def stoppages_reliability(request):
    return generic_module_view(request, 'Reliability Metrics & MTBF/MTTR', 'مؤشرات الاعتمادية الصناعية وMTBF/MTTR', 'Batch 4', [
        'MTBF (Mean Time Between Failures)',
        'MTTR (Mean Time To Repair)',
        'MTTF (Mean Time To Failure) and Failure Rate (lambda)',
    ], ['maintenance', 'supervisor', 'manager', 'admin'])


# Quality Secondary
@role_required('quality', 'supervisor', 'admin')
def quality_samples(request):
    return generic_module_view(request, 'Scale Weight Samples Registry', 'سجل عينات موازين الفحص', 'Batch 5', [
        'Raw checkweigher sample measurements in grams',
        'Tolerance checking against USL and LSL specifications',
    ], ['quality', 'supervisor', 'admin'])

@role_required('quality', 'supervisor', 'admin')
def quality_defects(request):
    return generic_module_view(request, 'Scrap & Defect Root Causes', 'سجل العيوب ونسب الهالك', 'Batch 5', [
        'Defect categorization (Underfill, Missing Cap, Damaged Label)',
        'Defect Pareto distribution and quarantine tracking',
    ], ['quality', 'supervisor', 'admin'])

@role_required('quality', 'manager', 'admin')
def quality_giveaway(request):
    return generic_module_view(request, 'Overfill Giveaway Financial Simulator', 'حاسبة الهدر المالي الناتج عن التعبئة الزائدة', 'Batch 5', [
        'Cumulative financial loss from bottle overfill',
        'Interactive recalibration slider modeling raw material savings',
    ], ['quality', 'manager', 'admin'])


# Planner Secondary
@role_required('planner', 'admin')
def planning_processes(request):
    return generic_module_view(request, 'Process Catalog & Routing Steps', 'دليل العمليات ومراحل التصنيع', 'Batch 2', [
        'Standard processes (Blow Molding, Filling, Capping, Labeling, Packing)',
        'Standard sequence and benchmark cycle times',
    ], ['planner', 'admin'])

@role_required('planner', 'admin')
def planning_rates(request):
    return generic_module_view(request, 'Machine-Product Rated Speed Matrix', 'مصفوفة السرعات المعيارية للماكينات والمنتجات', 'Batch 2', [
        'Specific CPM and cycle times per Machine x Product combination',
        'Effective-dated benchmark rate history',
    ], ['planner', 'admin'])

@role_required('planner', 'admin')
def planning_reasons(request):
    return generic_module_view(request, 'Stoppage & Defect Reason Taxonomies', 'تصنيف أسباب التوقفات والعيوب', 'Batch 2', [
        'Hierarchical stoppage taxonomy (Mechanical, Electrical, Operational, Materials)',
        'TPM Six Big Losses mapping and department attribution',
    ], ['planner', 'admin'])


# Supply Chain Secondary
@role_required('supply_chain', 'planner', 'admin')
def work_orders_schedule(request):
    return generic_module_view(request, 'Production Schedule Matrix', 'جدول الإنتاج الزمني', 'Batch 6', [
        'Shift-by-shift machine allocation timeline',
        'Target quantities and order completion pacing',
    ], ['supply_chain', 'planner', 'admin'])

@role_required('supply_chain', 'admin')
def work_orders_materials(request):
    return generic_module_view(request, 'Material Staging & Delivery Tracker', 'تتبع تسليم المواد الخام', 'Batch 6', [
        'Preforms, caps, labels, cartons delivery status',
        'BOM stage material readiness',
    ], ['supply_chain', 'admin'])

@role_required('supply_chain', 'admin')
def work_orders_erp_sync(request):
    return generic_module_view(request, 'ERP / Odoo Synchronization Queue', 'طابور مزامنة نظام ERP / أودو', 'Batch 6', [
        'External work order import status and retry engine',
        'Conflict queue and idempotency validation',
    ], ['supply_chain', 'admin'])


# Manager Secondary
@role_required('manager', 'admin')
def manager_losses(request):
    return generic_module_view(request, 'TPM Six Big Losses Financial Waterfall', 'شلال الخسائر الست الكبرى والتحليل المالي', 'Batch 5', [
        'Breakdown minutes and lost revenue across 6 TPM categories',
        'Lost output opportunity cost and actual scrap expense',
    ], ['manager', 'admin'])


# Admin Secondary
@role_required('admin')
def admin_users(request):
    from apps.accounts.models import User
    users = User.objects.prefetch_related('role_assignments__role').all()
    return render(request, 'portal/admin_users.html', {'users': users})

@role_required('admin')
def admin_roles(request):
    from apps.accounts.models import Role
    roles = Role.objects.all().order_by('sequence')
    return render(request, 'portal/admin_roles.html', {'roles': roles})

@role_required('admin')
def admin_machines(request):
    return generic_module_view(request, 'Machine Asset Setup', 'تهيئة الماكينات والأصول', 'Batch 2', [
        'Machine configuration, ideal CPM, line sequence',
        'Hardware pairing and critical constraint designation',
    ], ['admin'])

@role_required('admin')
def admin_settings(request):
    return generic_module_view(request, 'System Settings & Branding', 'إعدادات النظام والعلامة التجارية', 'Batch 8', [
        'Factory site parameters, timezone, currency',
        'Branding customization and theme preferences',
    ], ['admin'])

@role_required('admin')
def admin_gateways(request):
    return generic_module_view(request, 'IoT Gateways & QR Onboarding', 'بوابات إنترنت الأشياء والربط السريع عبر QR', 'Batch 2', [
        'Hardware token claim QR code generator',
        'ESP32, Raspberry Pi, and Moxa edge gateway status',
    ], ['admin'])

@role_required('admin')
def admin_integrations(request):
    return generic_module_view(request, 'External Integrations & Webhooks', 'التكامل الخارجي والربط البرمجي', 'Batch 8', [
        'ERP/MES API connectors',
        'Telegram Bot notification channels',
    ], ['admin'])

@role_required('admin')
def admin_audit(request):
    from apps.accounts.models import AuditEvent
    audit_events = AuditEvent.objects.select_related('actor').all()[:100]
    return render(request, 'portal/admin_audit.html', {'audit_events': audit_events})


# Controller Secondary
@role_required('controller', 'admin')
def controller_scenarios(request):
    return generic_module_view(request, 'Simulator Scenario Library', 'مكتبة سيناريوهات المحاكاة', 'Batch 3', [
        'Cap Chute Jam, Overfill Drift, Mechanical Breakdown, Defect Burst, Golden Run',
    ], ['controller', 'admin'])

@role_required('controller', 'admin')
def controller_machines(request):
    return generic_module_view(request, 'Simulator Machine Overrides', 'التحكم اليدوي في متغيرات الماكينات', 'Batch 3', [
        'Live sliders for CPM speed, vibration, temperature, and machine states',
    ], ['controller', 'admin'])

@role_required('controller', 'admin')
def controller_shift(request):
    return generic_module_view(request, 'Simulator Shift Rotation Control', 'التحكم في تدوير الورديات التجريبية', 'Batch 3', [
        'Instant shift end trigger and synthetic handover generation',
    ], ['controller', 'admin'])
