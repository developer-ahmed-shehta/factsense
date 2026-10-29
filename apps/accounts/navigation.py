"""
Navigation menu configuration and generator for all 9 canonical roles.
Matches Section 2.2 of the Master Specification (with Engineering & SOP Approvals removed).
"""

from django.urls import reverse
from .translations import get_translation

# Canonical role navigation structure
# Each item: (label_key, url_name, is_more)
ROLE_NAV_CONFIG = {
    'operator': [
        ('nav_my_machine', 'operator_home', False),
        ('nav_production', 'operator_production', False),
        ('nav_stoppages', 'operator_stoppages', False),
    ],
    'supervisor': [
        ('nav_floor', 'floor_home', False),
        ('nav_shifts', 'shifts_home', False),
        ('nav_stoppages', 'stoppages_home', False),
        ('nav_maintenance', 'maintenance_home', False),
        ('nav_reports', 'reports_home', False),
        # More dropdown items
        ('nav_smed', 'smed_home', True),
        ('nav_alerts', 'alerts_home', True),
        ('nav_copilot', 'copilot_home', True),
    ],
    'maintenance': [
        ('nav_tickets', 'maintenance_home', False),
        ('nav_machines', 'maintenance_machines', False),
        ('nav_spares', 'maintenance_spares', False),
        ('nav_history', 'maintenance_history', False),
        # More dropdown items
        ('nav_reliability', 'stoppages_reliability', True),
        ('nav_alerts', 'alerts_home', True),
        ('nav_copilot', 'copilot_home', True),
    ],
    'quality': [
        ('nav_quality', 'quality_home', False),
        ('nav_samples', 'quality_samples', False),
        ('nav_defects', 'quality_defects', False),
        # More dropdown items
        ('nav_giveaway', 'quality_giveaway', True),
        ('nav_reports', 'reports_home', True),
        ('nav_alerts', 'alerts_home', True),
        ('nav_copilot', 'copilot_home', True),
    ],
    'planner': [
        ('nav_products', 'products_list', False),
        ('nav_shifts', 'shifts_home', False),
        ('nav_reasons', 'planning_reasons', False),
        ('nav_alerts', 'alerts_home', False),
        ('nav_machines', 'admin_machines', False),
        ('nav_work_orders', 'work_orders_home', False),
        ('nav_processes', 'planning_processes', False),
        ('nav_reports', 'reports_home', False),
        ('nav_history', 'admin_audit', False),
    ],
    'supply_chain': [
        ('nav_work_orders', 'work_orders_home', False),
        ('nav_schedule', 'work_orders_schedule', False),
        ('nav_materials', 'work_orders_materials', False),
        ('nav_erp_sync', 'work_orders_erp_sync', False),
        ('nav_reports', 'reports_home', False),
    ],
    'manager': [
        ('nav_overview', 'manager_home', False),
        ('nav_floor', 'floor_home', False),
        ('nav_reports', 'reports_home', False),
        # More dropdown items
        ('nav_quality', 'quality_home', True),
        ('nav_losses', 'manager_losses', True),
        ('nav_alerts', 'alerts_home', True),
        ('nav_copilot', 'copilot_home', True),
    ],
    'admin': [
        ('nav_users', 'admin_users', False),
        ('nav_roles', 'admin_roles', False),
        ('nav_machines', 'admin_machines', False),
        ('nav_products', 'products_list', False),
        ('nav_settings', 'admin_settings', False),
        # More dropdown items
        ('nav_gateways', 'admin_gateways', True),
        ('nav_integrations', 'admin_integrations', True),
        ('nav_audit', 'admin_audit', True),
    ],
    'controller': [
        ('nav_simulation', 'controller_home', False),
        ('nav_scenarios', 'controller_scenarios', False),
        ('nav_machines', 'controller_machines', False),
        ('nav_shift_control', 'controller_shift', False),
    ],
}


def get_navigation_for_role(role_code, current_path='', lang='en'):
    """
    Builds the navigation structure for a specific role.
    Splits items into primary horizontal links and 'More' dropdown items.
    """
    items = ROLE_NAV_CONFIG.get(role_code, [])
    primary_links = []
    more_links = []

    for label_key, url_name, is_more in items:
        try:
            url = reverse(url_name)
        except Exception:
            url = f"/{url_name}/"
            
        label = get_translation(label_key, lang=lang)
        is_active = (current_path == url or (url != '/' and current_path.startswith(url)))

        link_item = {
            'label': label,
            'url_name': url_name,
            'url': url,
            'is_active': is_active,
        }

        if is_more:
            more_links.append(link_item)
        else:
            primary_links.append(link_item)

    return {
        'primary': primary_links,
        'more': more_links,
        'has_more': len(more_links) > 0,
    }
