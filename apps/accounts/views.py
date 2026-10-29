"""
Authentication, multi-role switching, and landing resolution views.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from .models import User, Role, AuditEvent
from .translations import get_translation


def login_view(request):
    """
    User login view with support for password authentication and quick demo credentials.
    """
    if request.user.is_authenticated:
        return redirect('role_landing')

    lang = request.session.get('django_language', 'en')
    next_url = request.GET.get('next', '')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                
                # Resolve role assignments
                assignments = list(user.role_assignments.filter(is_active=True).select_related('role'))
                if assignments:
                    # Default to first role or keep last active role
                    initial_role = assignments[0].role.code
                    request.session['active_role'] = initial_role
                    destination = assignments[0].role.default_landing
                elif user.is_superuser:
                    request.session['active_role'] = 'admin'
                    destination = '/administration/'
                else:
                    request.session['active_role'] = None
                    destination = '/'

                # Audit login
                AuditEvent.objects.create(
                    actor=user,
                    active_role=request.session.get('active_role', ''),
                    action='USER_LOGIN',
                    resource='Session',
                    details={'method': 'credentials', 'next': next_url}
                )

                if next_url:
                    return redirect(next_url)
                return redirect(destination)
            else:
                messages.error(request, 'This user account is inactive.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html', {
        'next_url': next_url,
    })


def logout_view(request):
    """
    Signs out user, clears session active_role, and redirects to login.
    """
    if request.user.is_authenticated:
        AuditEvent.objects.create(
            actor=request.user,
            active_role=request.session.get('active_role', ''),
            action='USER_LOGOUT',
            resource='Session'
        )
    logout(request)
    request.session.flush()
    return redirect('login')


@require_http_methods(['GET', 'POST'])
def switch_role_view(request):
    """
    Switches persona for users with multiple role assignments.
    Validates that user has explicit assignment before switching.
    """
    if not request.user.is_authenticated:
        return redirect('login')

    target_role_code = request.POST.get('role_code') or request.GET.get('role_code')
    if not target_role_code:
        # Show persona selection page
        return render(request, 'accounts/switch_role.html')

    # Verify authorization
    user_roles = [a.role.code for a in request.user.role_assignments.filter(is_active=True).select_related('role')]
    if request.user.is_superuser and 'admin' not in user_roles:
        user_roles.append('admin')

    if target_role_code not in user_roles:
        messages.error(request, f"You are not assigned to role '{target_role_code}'. Persona switch denied.")
        return redirect(request.META.get('HTTP_REFERER', 'role_landing'))

    # Update active persona in session
    previous_role = request.session.get('active_role')
    request.session['active_role'] = target_role_code

    # Audit persona switch
    AuditEvent.objects.create(
        actor=request.user,
        active_role=target_role_code,
        action='SWITCH_PERSONA',
        resource='Role',
        resource_id=target_role_code,
        details={'previous_role': previous_role, 'new_role': target_role_code}
    )

    # Redirect to target role's landing page
    role_obj = Role.objects.filter(code=target_role_code).first()
    landing = role_obj.default_landing if role_obj else 'role_landing'

    messages.success(request, f"Switched active persona to {role_obj.name if role_obj else target_role_code}.")
    return redirect(landing)


def quick_demo_login_view(request, username):
    """
    Development/Reviewer shortcut: 1-click login into any seeded demo persona.
    """
    user = User.objects.filter(username=username).first()
    if not user:
        messages.error(request, f"Demo account '{username}' does not exist.")
        return redirect('login')

    login(request, user)
    
    # Resolve role assignments
    assignments = list(user.role_assignments.filter(is_active=True).select_related('role'))
    if assignments:
        initial_role = assignments[0].role.code
        request.session['active_role'] = initial_role
        destination = assignments[0].role.default_landing
    elif user.is_superuser:
        request.session['active_role'] = 'admin'
        destination = '/administration/'
    else:
        destination = '/'

    # Audit login
    AuditEvent.objects.create(
        actor=user,
        active_role=request.session.get('active_role', ''),
        action='DEMO_QUICK_LOGIN',
        resource='Session',
        details={'username': username}
    )

    messages.info(request, f"Logged in as {user.get_display_name()} [{request.session.get('active_role')}].")
    return redirect(destination)


def set_language_view(request):
    """
    Switches interface language between English and Arabic without losing page context.
    Uses standard Django i18n activation and cookie/session persistence.
    """
    from django.utils import translation
    from django.conf import settings
    
    lang = request.GET.get('lang', 'en')
    if lang in ['en', 'ar']:
        translation.activate(lang)
        request.session['django_language'] = lang
        if request.user.is_authenticated:
            request.user.preferred_language = lang
            request.user.save(update_fields=['preferred_language'])

    referer = request.META.get('HTTP_REFERER')
    response = HttpResponseRedirect(referer) if referer else redirect('role_landing')
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang)
    return response


def role_landing_view(request):
    """
    Root landing dispatcher: dynamically resolves user's home based on active_role.
    Strictly avoids hardcoded cascading if/elif redirects.
    """
    if not request.user.is_authenticated:
        return redirect('login')

    active_role = getattr(request, 'active_role', None)
    if not active_role:
        # Check if user has assignments
        assignments = list(request.user.role_assignments.filter(is_active=True).select_related('role'))
        if assignments:
            active_role = assignments[0].role.code
            request.session['active_role'] = active_role
        elif request.user.is_superuser:
            active_role = 'admin'
            request.session['active_role'] = 'admin'

    if active_role:
        role_obj = Role.objects.filter(code=active_role).first()
        if role_obj and role_obj.default_landing:
            return redirect(role_obj.default_landing)

    # Fallback to general dashboard or login
    return redirect('login')
