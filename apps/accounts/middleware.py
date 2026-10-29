"""
RoleMiddleware and localization handler.
Enforces active role persistence, session security, and RTL direction.
"""

from .models import Role, UserRoleAssignment


class RoleMiddleware:
    """
    Validates and maintains the user's active_role persona server-side on every request.
    Prevents role escalation and automatically provisions active persona context.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Handle Language & Direction with standard Django translation
        from django.utils import translation
        from django.conf import settings

        lang_param = request.GET.get('lang')
        if lang_param in ['en', 'ar']:
            request.session['django_language'] = lang_param
            if request.user.is_authenticated and hasattr(request.user, 'preferred_language'):
                if request.user.preferred_language != lang_param:
                    request.user.preferred_language = lang_param
                    request.user.save(update_fields=['preferred_language'])

        current_lang = request.session.get('django_language')
        if not current_lang:
            if request.user.is_authenticated and getattr(request.user, 'preferred_language', None):
                current_lang = request.user.preferred_language
            else:
                current_lang = translation.get_language_from_request(request)
        if current_lang not in ['en', 'ar']:
            current_lang = 'en'
        
        translation.activate(current_lang)
        request.LANGUAGE_CODE = current_lang
        request.IS_RTL = (current_lang == 'ar')

        # 2. Handle User Role & Active Persona
        request.active_role = None
        request.active_role_obj = None
        request.user_roles = []
        request.active_assignment = None

        if request.user.is_authenticated:
            # Query all active role assignments for this user
            assignments = list(
                UserRoleAssignment.objects.filter(user=request.user, is_active=True)
                .select_related('role', 'factory', 'line', 'machine')
            )
            
            user_roles = [a.role for a in assignments]
            request.user_roles = user_roles
            allowed_role_codes = [r.code for r in user_roles]

            # If user is superuser and has no assignments, grant admin role
            if request.user.is_superuser and not allowed_role_codes:
                admin_role, _ = Role.objects.get_or_create(
                    code='admin',
                    defaults={
                        'name': 'System Administrator',
                        'name_ar': 'مسؤول النظام',
                        'default_landing': '/administration/',
                        'sequence': 90
                    }
                )
                user_roles = [admin_role]
                request.user_roles = user_roles
                allowed_role_codes = ['admin']

            # Resolve active role from session
            session_role = request.session.get('active_role')

            if session_role and session_role in allowed_role_codes:
                active_role = session_role
            elif allowed_role_codes:
                active_role = allowed_role_codes[0]
                request.session['active_role'] = active_role
            else:
                active_role = None
                request.session['active_role'] = None

            request.active_role = active_role

            if active_role:
                # Find matching Role object
                for r in user_roles:
                    if r.code == active_role:
                        request.active_role_obj = r
                        break
                # Find matching Assignment
                for a in assignments:
                    if a.role.code == active_role:
                        request.active_assignment = a
                        break

        response = self.get_response(request)
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, current_lang)
        return response
