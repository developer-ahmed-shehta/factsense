"""
Views and API Endpoints for FactSense Industrial AI Copilot.
Fulfills F09 and Batch 7 specifications. Zero-emoji compliant.
"""

import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from apps.accounts.decorators import role_required
from apps.masterdata.models import Line
from apps.copilot.models import CopilotChatSession, CopilotChatMessage
from apps.copilot.services.dual_engine import ask_industrial_copilot, get_quick_executive_summary


@role_required('supervisor', 'maintenance', 'quality', 'planner', 'supply_chain', 'manager', 'admin')
def copilot_view(request):
    """
    Industrial AI Copilot conversational portal (/copilot/).
    """
    lines = Line.objects.all()
    selected_line_id = request.GET.get('line')
    selected_line = Line.objects.filter(id=selected_line_id).first() if selected_line_id else lines.first()

    # Get or create active session for user
    session = CopilotChatSession.objects.filter(user=request.user, line=selected_line).first()
    if not session:
        session = CopilotChatSession.objects.create(
            user=request.user,
            line=selected_line,
            title=f"Industrial Chat ({selected_line.name if selected_line else 'Global'})"
        )

    messages = session.messages.all().order_by('created_at')
    quick_summary = get_quick_executive_summary(line=selected_line, lang=request.LANGUAGE_CODE)

    context = {
        'page_title': 'Industrial AI Copilot',
        'page_title_ar': 'المساعد الصناعي الذكي (Dual-Engine AI)',
        'lines': lines,
        'selected_line': selected_line,
        'session': session,
        'messages': messages,
        'quick_summary': quick_summary,
    }
    return render(request, 'copilot/copilot_home.html', context)


@role_required('supervisor', 'maintenance', 'quality', 'planner', 'supply_chain', 'manager', 'admin')
@require_POST
def copilot_chat_api(request):
    """
    Bilingual chat API endpoint (POST /copilot/api/chat/).
    Payload: {"query": "...", "line_id": "...", "session_id": "..."}
    Returns: {"answer": "...", "action_chips": [...], "engine_used": "...", "language": "..."}
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    query = data.get('query', '').strip()
    if not query:
        return JsonResponse({'error': 'Query text is required'}, status=400)

    line_id = data.get('line_id')
    line = Line.objects.filter(id=line_id).first() if line_id else Line.objects.first()

    session_id = data.get('session_id')
    session = CopilotChatSession.objects.filter(id=session_id).first() if session_id else None
    if not session:
        session = CopilotChatSession.objects.create(user=request.user, line=line, title='Industrial Copilot Session')

    # Save user query
    CopilotChatMessage.objects.create(
        session=session,
        role='user',
        content=query
    )

    # Execute Copilot Dual Engine
    result = ask_industrial_copilot(query, line=line, user=request.user)

    # Save AI response
    CopilotChatMessage.objects.create(
        session=session,
        role='assistant',
        content=result['answer'],
        action_chips=result['action_chips'],
        engine_used=result['engine_used']
    )

    return JsonResponse({
        'answer': result['answer'],
        'action_chips': result['action_chips'],
        'engine_used': result['engine_used'],
        'language': result['language'],
        'session_id': str(session.id),
    })


@role_required('supervisor', 'maintenance', 'quality', 'planner', 'supply_chain', 'manager', 'admin')
@require_GET
def copilot_quick_summary_api(request):
    """
    1-Sentence executive status check API (GET /copilot/api/quick-summary/?line_code=...).
    """
    line_code = request.GET.get('line_code')
    line = Line.objects.filter(code=line_code).first() if line_code else Line.objects.first()
    lang = request.GET.get('lang', request.LANGUAGE_CODE)

    data = get_quick_executive_summary(line=line, lang=lang)
    return JsonResponse(data)
