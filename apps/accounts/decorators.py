"""
Security decorators and mixins for role-based and scope-based authorization.
"""

from functools import wraps
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.mixins import AccessMixin


def role_required(*allowed_roles):
    """
    Decorator enforcing that the request actor is authenticated and their
    active_role persona is included in allowed_roles.
    Returns 403 Forbidden if not authorized.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            active_role = getattr(request, 'active_role', None)

            # Superusers with no active role default to admin
            if request.user.is_superuser and not active_role:
                active_role = 'admin'

            if not active_role or active_role not in allowed_roles:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/api/'):
                    return JsonResponse({
                        'error': 'Forbidden',
                        'message': f"Active role '{active_role}' is not authorized. Allowed roles: {list(allowed_roles)}",
                        'status': 403
                    }, status=403)
                
                context = {
                    'active_role': active_role,
                    'allowed_roles': allowed_roles,
                    'attempted_path': request.path,
                }
                return render(request, 'accounts/403.html', context, status=403)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


class RoleRequiredMixin(AccessMixin):
    """
    CBV mixin enforcing that user's active_role is in allowed_roles.
    """
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        active_role = getattr(request, 'active_role', None)
        if request.user.is_superuser and not active_role:
            active_role = 'admin'

        if not active_role or (self.allowed_roles and active_role not in self.allowed_roles):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/api/'):
                return JsonResponse({
                    'error': 'Forbidden',
                    'message': f"Active role '{active_role}' is not authorized. Allowed: {self.allowed_roles}",
                    'status': 403
                }, status=403)

            context = {
                'active_role': active_role,
                'allowed_roles': self.allowed_roles,
                'attempted_path': request.path,
            }
            return render(request, 'accounts/403.html', context, status=403)

        return super().dispatch(request, *args, **kwargs)
