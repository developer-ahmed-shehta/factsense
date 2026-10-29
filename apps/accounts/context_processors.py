"""
Context processors providing global template state:
active role, navigation, language/RTL, translations, and demo switcher personas.
"""

from .navigation import get_navigation_for_role
from .translations import TRANSLATIONS, get_translation

DEMO_PERSONAS = [
    {'username': 'operator_demo', 'role_code': 'operator', 'label': 'Line Operator (مشغل)', 'badge': 'Operator'},
    {'username': 'supervisor_demo', 'role_code': 'supervisor', 'label': 'Shift Supervisor (مشرف)', 'badge': 'Supervisor'},
    {'username': 'maintenance_demo', 'role_code': 'maintenance', 'label': 'Maintenance Tech (صيانة)', 'badge': 'Maintenance'},
    {'username': 'quality_demo', 'role_code': 'quality', 'label': 'Quality Specialist (جودة)', 'badge': 'Quality'},
    {'username': 'planner_demo', 'role_code': 'planner', 'label': 'Production Planner (تخطيط)', 'badge': 'Planner'},
    {'username': 'supply_demo', 'role_code': 'supply_chain', 'label': 'Supply Chain Officer (إمداد)', 'badge': 'Supply Chain'},
    {'username': 'manager_demo', 'role_code': 'manager', 'label': 'Plant Director (مدير)', 'badge': 'Manager'},
    {'username': 'admin_demo', 'role_code': 'admin', 'label': 'System Admin (مسؤول)', 'badge': 'Admin'},
    {'username': 'controller_demo', 'role_code': 'controller', 'label': 'Demo Master (محاكاة)', 'badge': 'Controller'},
    {'username': 'lead_tech', 'role_code': 'supervisor', 'label': 'Lead Tech (Multi: Supervisor + Maint)', 'badge': 'Multi-Role'},
    {'username': 'ops_manager', 'role_code': 'manager', 'label': 'Ops Head (Multi: Manager + Planner)', 'badge': 'Multi-Role'},
]


def active_role_context(request):
    """
    Supplies active persona, navigation hierarchy, translations, and demo accounts.
    """
    lang = getattr(request, 'LANGUAGE_CODE', 'en')
    is_rtl = getattr(request, 'IS_RTL', False)
    active_role = getattr(request, 'active_role', None)
    active_role_obj = getattr(request, 'active_role_obj', None)
    user_roles = getattr(request, 'user_roles', [])
    active_assignment = getattr(request, 'active_assignment', None)

    # Translation dictionary for the active language
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en'])

    # Build active navigation
    navigation = None
    if active_role:
        navigation = get_navigation_for_role(active_role, current_path=request.path, lang=lang)

    return {
        'lang': lang,
        'is_rtl': is_rtl,
        'active_role': active_role,
        'active_role_obj': active_role_obj,
        'user_roles': user_roles,
        'has_multiple_roles': len(user_roles) > 1,
        'active_assignment': active_assignment,
        'nav': navigation,
        'demo_personas': DEMO_PERSONAS,
        't': t,
    }


def branding_context(request):
    """
    System branding tokens and metadata.
    """
    return {
        'BRAND_NAME': 'FactSense',
        'BRAND_TAGLINE': 'Smart Factory MES & IIoT Platform',
        'APP_VERSION': 'v1.1 (Batch 1)',
        'CURRENT_YEAR': 2026,
    }
