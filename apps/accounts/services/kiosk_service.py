"""
Kiosk Session Exclusivity & Force-Logout Lockout Service.
Fulfills F19, F20 and Batch 8 hardening requirements:
- One-operator-per-machine exclusivity enforcement
- Force-logout lockout on critical failure reasons (force_logout=True)
- Maintenance lock blocking operator sessions
- Physical kiosk session handover and supervisor release
"""

from django.utils import timezone
from apps.accounts.models import OperatorSession, AuditEvent
from apps.operations.services.maintenance_service import is_machine_locked_by_maintenance
from apps.telemetry.models import DowntimeEvent


def check_machine_force_logout(machine):
    """
    Checks if a machine is currently subject to a safety force-logout lockout.
    Lockout is triggered by:
    1. Active maintenance lock (machine under repair or testing).
    2. Open downtime event classified with a StoppageReason having force_logout=True
       (e.g., critical bearing failure, high-voltage trip).
    Returns (is_locked_out, reason_message).
    """
    if not machine:
        return False, None

    # Check 1: Maintenance lock
    if is_machine_locked_by_maintenance(machine):
        return True, "Machine is currently locked under active maintenance repair/testing."

    # Check 2: Open downtime event with force_logout=True
    open_stop = DowntimeEvent.objects.filter(
        machine=machine,
        end_time__isnull=True,
        reason__isnull=False
    ).select_related('reason').order_by('-start_time').first()

    if open_stop and open_stop.reason and open_stop.reason.force_logout:
        return True, f"Safety Lockout: Active stoppage '{open_stop.reason.name}' requires operator logout."

    return False, None


def check_kiosk_exclusivity(user, machine, session_key):
    """
    Validates whether the user is permitted to operate the specified machine.
    Returns:
    {
        'allowed': bool,
        'conflict': bool,
        'active_session': OperatorSession or None,
        'locked_out': bool,
        'lockout_reason': str or None,
        'message': str
    }
    """
    if not machine or not user or not user.is_authenticated:
        return {
            'allowed': False,
            'conflict': False,
            'active_session': None,
            'locked_out': False,
            'lockout_reason': None,
            'message': 'Invalid machine or user.'
        }

    # 1. Check force-logout safety lockout
    is_locked_out, lockout_reason = check_machine_force_logout(machine)
    if is_locked_out:
        # Invalidate any open sessions on this locked machine
        force_terminate_machine_sessions(machine, reason=lockout_reason, actor=user)
        return {
            'allowed': False,
            'conflict': False,
            'active_session': None,
            'locked_out': True,
            'lockout_reason': lockout_reason,
            'message': lockout_reason
        }

    # 2. Check existing active operator sessions on this machine
    active_session = OperatorSession.objects.filter(
        machine=machine,
        is_active=True
    ).select_related('operator').first()

    if not active_session:
        # No conflict - machine is available
        return {
            'allowed': True,
            'conflict': False,
            'active_session': None,
            'locked_out': False,
            'lockout_reason': None,
            'message': 'Machine is free for operation.'
        }

    # If the active session belongs to the current user (same user, possibly same or resumed browser session)
    if active_session.operator_id == user.id:
        return {
            'allowed': True,
            'conflict': False,
            'active_session': active_session,
            'locked_out': False,
            'lockout_reason': None,
            'message': 'Active session resumes.'
        }

    # If another operator is active on this machine -> EXCLUSIVE CONFLICT!
    other_operator_name = active_session.operator.get_full_name() or active_session.operator.username
    conflict_msg = (
        f"Exclusive Session Conflict: Machine {machine.code} is currently claimed by "
        f"{other_operator_name} (since {active_session.started_at.strftime('%H:%M')}). "
        f"Operator sign-off or Supervisor release is required."
    )

    # Log audit event for conflict
    AuditEvent.objects.create(
        actor=user,
        active_role='operator',
        action='KIOSK_SESSION_CONFLICT',
        resource='Machine',
        resource_id=machine.code,
        scope_factory=machine.line.factory.code if machine.line and machine.line.factory else '',
        scope_line=machine.line.code if machine.line else '',
        details={
            'machine_code': machine.code,
            'conflicting_operator': other_operator_name,
            'started_at': active_session.started_at.isoformat(),
        }
    )

    return {
        'allowed': False,
        'conflict': True,
        'active_session': active_session,
        'locked_out': False,
        'lockout_reason': None,
        'message': conflict_msg
    }


def claim_operator_session(user, machine, session_key):
    """
    Claims exclusive operation of a machine for an operator.
    """
    if not user or not machine or not user.is_authenticated:
        return None, "Invalid user or machine"

    # Verify exclusivity
    check = check_kiosk_exclusivity(user, machine, session_key)
    if not check['allowed']:
        return None, check['message']

    # Close any other active sessions this user had on OTHER machines (one operator cannot operate two machines at once)
    OperatorSession.objects.filter(
        operator=user,
        is_active=True
    ).exclude(machine=machine).update(
        is_active=False,
        ended_at=timezone.now()
    )

    # Get or create active session on this machine
    session, created = OperatorSession.objects.get_or_create(
        operator=user,
        machine=machine,
        is_active=True,
        defaults={
            'session_key': session_key or '',
            'started_at': timezone.now()
        }
    )

    if created:
        AuditEvent.objects.create(
            actor=user,
            active_role='operator',
            action='KIOSK_CLAIM_SESSION',
            resource='Machine',
            resource_id=machine.code,
            scope_factory=machine.line.factory.code if machine.line and machine.line.factory else '',
            scope_line=machine.line.code if machine.line else '',
            details={
                'machine_code': machine.code,
                'session_id': str(session.id),
            }
        )

    return session, "Session claimed successfully."


def release_operator_session(user, machine, supervisor_override=False):
    """
    Releases the active operator session on a machine.
    Can be initiated by the operator themselves, or by a supervisor/admin.
    """
    query = OperatorSession.objects.filter(machine=machine, is_active=True)
    if not supervisor_override:
        query = query.filter(operator=user)

    active_sessions = list(query)
    for session in active_sessions:
        session.is_active = False
        session.ended_at = timezone.now()
        session.save(update_fields=['is_active', 'ended_at'])

        action_name = 'KIOSK_SUPERVISOR_OVERRIDE_RELEASE' if supervisor_override else 'KIOSK_RELEASE_SESSION'
        AuditEvent.objects.create(
            actor=user,
            active_role='supervisor' if supervisor_override else 'operator',
            action=action_name,
            resource='Machine',
            resource_id=machine.code,
            scope_factory=machine.line.factory.code if machine.line and machine.line.factory else '',
            scope_line=machine.line.code if machine.line else '',
            details={
                'machine_code': machine.code,
                'session_id': str(session.id),
                'operator_id': str(session.operator_id),
                'override': supervisor_override,
            }
        )

    return len(active_sessions) > 0


def force_terminate_machine_sessions(machine, reason="Safety force-logout", actor=None):
    """
    Forcefully terminates all active operator sessions on a machine due to safety or maintenance lock.
    """
    sessions = OperatorSession.objects.filter(machine=machine, is_active=True)
    count = 0
    now = timezone.now()
    for s in sessions:
        s.is_active = False
        s.ended_at = now
        s.save(update_fields=['is_active', 'ended_at'])
        count += 1

        AuditEvent.objects.create(
            actor=actor,
            active_role='system',
            action='KIOSK_FORCE_LOGOUT_LOCKOUT',
            resource='Machine',
            resource_id=machine.code,
            scope_factory=machine.line.factory.code if machine.line and machine.line.factory else '',
            scope_line=machine.line.code if machine.line else '',
            details={
                'machine_code': machine.code,
                'session_id': str(s.id),
                'operator_id': str(s.operator_id),
                'reason': reason,
            }
        )
    return count
