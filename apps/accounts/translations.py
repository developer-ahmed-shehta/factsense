"""
Bilingual translation integration for FactSense MES platform.
Bridges to standard Django i18n and the root locale/ directory catalogs (django.po / django.mo).
"""

from django.utils.translation import gettext as _, override, get_language

# Mapping internal navigation and UI keys to canonical gettext msgid strings
KEY_TO_MSGID = {
    # Brand & Global
    'brand_name': 'FactSense',
    'brand_subtitle': 'Industrial MES & IIoT Platform',
    'more': 'More',
    'logout': 'Logout',
    'login': 'Sign In',
    'switch_role': 'Switch Role Persona',
    'active_persona': 'Active Persona',
    'current_role': 'Current Role',
    'other_assigned_roles': 'Other Assigned Roles',
    'quick_demo_bar': 'Developer Demo Persona Switcher (Batch 1 Review)',
    'all_roles_demo': 'Quick Login as Demo Persona',
    'actions': 'Actions',
    'edit': 'Edit',
    'delete': 'Delete',
    'archive': 'Archive',
    'save': 'Save',
    'cancel': 'Cancel',
    'close': 'Close',
    'status': 'Status',
    'active': 'Active',
    'inactive': 'Inactive',
    'archived': 'Archived',
    'view_only': 'View Only',
    'access_denied': 'Access Denied (403)',
    'access_denied_msg': 'Your active persona does not have permission to access this module.',
    'switch_persona_suggestion': 'If you have an assigned role for this area, please switch personas using the account menu.',
    'back_to_home': 'Back to My Home',

    # Canonical Role Names
    'role_operator': 'Line Operator',
    'role_supervisor': 'Shift Supervisor',
    'role_maintenance': 'Maintenance Technician',
    'role_quality': 'Quality Specialist',
    'role_planner': 'Production Planner',
    'role_supply_chain': 'Supply Chain Officer',
    'role_manager': 'Plant Director',
    'role_admin': 'System Administrator',
    'role_controller': 'Simulator Controller',

    # Navigation Items
    'nav_my_machine': 'My Machine',
    'nav_production': 'Production',
    'nav_stoppages': 'Stoppages',
    'nav_documents': 'Documents',
    'nav_floor': 'Floor',
    'nav_shifts': 'Shifts',
    'nav_maintenance': 'Maintenance',
    'nav_reports': 'Reports',
    'nav_smed': 'SMED',
    'nav_alerts': 'Alerts',
    'nav_copilot': 'Copilot',
    'nav_tickets': 'Tickets',
    'nav_machines': 'Machines',
    'nav_spares': 'Spare Requests',
    'nav_history': 'History',
    'nav_reliability': 'Reliability',
    'nav_quality': 'Quality',
    'nav_samples': 'Samples',
    'nav_defects': 'Defects',
    'nav_giveaway': 'Giveaway',
    'nav_products': 'Products',
    'nav_work_orders': 'Work Orders',
    'nav_processes': 'Processes',
    'nav_rates': 'Rates',
    'nav_reasons': 'Stoppage Reasons',
    'nav_schedule': 'Schedule',
    'nav_materials': 'Materials',
    'nav_erp_sync': 'ERP Sync',
    'nav_overview': 'Overview',
    'nav_losses': 'Losses',
    'nav_users': 'Users',
    'nav_roles': 'Roles',
    'nav_settings': 'Settings',
    'nav_gateways': 'Gateways',
    'nav_integrations': 'Integrations',
    'nav_audit': 'Historical Data',
    'nav_simulation': 'Simulation',
    'nav_scenarios': 'Scenarios',
    'nav_shift_control': 'Shift Control',

    # Product Management Page (Section 2.4 reference)
    'pm_title': 'Product Management',
    'pm_subtitle': 'Manage all company products and specifications',
    'pm_add_product': 'Add Product',
    'pm_col_name': 'NAME',
    'pm_col_code': 'CODE',
    'pm_col_uom': 'UOM',
    'pm_col_sop': 'DESIGN LINK',
    'pm_col_cycle_time': 'IDEAL CYCLE TIME [MINUTE]',
    'pm_col_processes': 'PROCESSES',
    'pm_col_actions': 'ACTIONS',
    'pm_search_placeholder': 'Search product by name or code...',
    'pm_all_categories': 'All Categories',
    'pm_empty_state_title': 'No Products Configured',
    'pm_empty_state_desc': 'Add your first production SKU to begin tracking cycle times and routings.',
    'pm_modal_add_title': 'Add New Product (SKU)',
    'pm_modal_edit_title': 'Edit Product',
    'pm_field_name_en': 'Product Name *',
    'pm_field_name_ar': 'Product Name *',
    'pm_field_code': 'Product Code',
    'pm_field_category': 'Category',
    'pm_field_uom': 'Unit of Measure (UOM)',
    'pm_field_cycle_time': 'Ideal Cycle Time [Minute]',
    'pm_field_rated_speed': 'Rated Speed (CPM)',
    'pm_field_sop_title': 'Design Reference',
    'pm_field_processes': 'Processes',
    'pm_save_success': 'Product saved successfully.',
    'pm_archive_confirm': 'Are you sure you want to delete this product? Historical data will be preserved.',
    'pm_archive_success': 'Product archived successfully.',
}


def get_translation(key, lang=None, default=''):
    """
    Standard Django i18n translation resolver from locale catalog.
    If lang is provided, resolves string for that language; otherwise uses active locale.
    """
    msgid = KEY_TO_MSGID.get(key, key)
    if lang:
        with override(lang):
            return _(msgid)
    return _(msgid)


class DynamicLocaleCatalog(dict):
    """
    Dynamic dictionary proxy that resolves keys via Django gettext i18n
    backed by root locale/ catalogs.
    """
    def __init__(self, lang=None):
        super().__init__()
        self.lang = lang

    def __getitem__(self, key):
        return get_translation(key, lang=self.lang)

    def get(self, key, default=None):
        msgid = KEY_TO_MSGID.get(key)
        if msgid is not None:
            return get_translation(key, lang=self.lang)
        if default is not None:
            return default
        return get_translation(key, lang=self.lang)


# Dynamic mapping for templates or legacy accesses
TRANSLATIONS = {
    'en': DynamicLocaleCatalog(lang='en'),
    'ar': DynamicLocaleCatalog(lang='ar'),
}
