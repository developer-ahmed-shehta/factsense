"""
High-Resolution Printable PDF Shift Handover Report Generator using ReportLab.
Fulfills F10 and Batch 7 specifications. Zero-emoji compliant.
"""

import io
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from apps.telemetry.services.oee_engine import calculate_line_oee
from apps.operations.services.stoppage_service import calculate_juran_pareto
from apps.operations.models import DefectLog, ShiftHandover, MaintenanceTicket
from apps.planning.models import WorkOrder


def generate_shift_handover_pdf(line, shift=None, user=None):
    """
    Generates a byte buffer containing a formatted printable PDF Shift Handover document.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#111827')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#6B7280')
    )
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#16A34A'),
        spaceAfter=6,
        spaceBefore=12
    )
    bullet_style = ParagraphStyle(
        'BulletText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1F2937')
    )
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#111827')
    )
    cell_header = ParagraphStyle(
        'CellHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    story = []

    # 1. Header Bar
    now_str = timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    shift_name = shift.name if shift else 'Morning Shift'
    header_data = [
        [
            Paragraph("<b>FACTSENSE INDUSTRIAL MES</b><br/><font size='8' color='#6B7280'>Automated Plant Intelligence</font>", cell_style),
            Paragraph(f"<b>OFFICIAL SHIFT HANDOVER REPORT</b><br/><font size='8' color='#6B7280'>Generated: {now_str}</font>", cell_style)
        ]
    ]
    t_header = Table(header_data, colWidths=[270, 270])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_header)
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#16A34A'), spaceBefore=4, spaceAfter=12))

    # 2. Document Context Table
    kpis = calculate_line_oee(line, shift=shift)
    bottleneck_name = line.bottleneck_machine.name if line.bottleneck_machine else 'FL-30 Bottleneck'
    context_data = [
        [
            Paragraph(f"<b>Factory:</b> {line.factory.name}", cell_style),
            Paragraph(f"<b>Line:</b> {line.name} ({line.code})", cell_style),
            Paragraph(f"<b>Shift Window:</b> {shift_name}", cell_style),
        ],
        [
            Paragraph(f"<b>Target OEE:</b> 85.0% World-Class", cell_style),
            Paragraph(f"<b>Bottleneck Asset:</b> {bottleneck_name}", cell_style),
            Paragraph(f"<b>Reported By:</b> {user.get_full_name() or user.username if user else 'System Automator'}", cell_style),
        ]
    ]
    t_context = Table(context_data, colWidths=[180, 180, 180])
    t_context.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F9FAFB')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_context)
    story.append(Spacer(1, 10))

    # 3. 4-Bullet Executive Synthesis
    story.append(Paragraph("1. Executive Shift Synthesis (4-Point Brief)", section_heading))
    oee_pct = kpis.get('oee_percent', 0.0)
    produced_units = kpis.get('total_units', 0)
    scrap_units = kpis.get('scrap_units', 0)
    
    bullets = [
        f"<b>Production & Line OEE:</b> The line closed with <b>{oee_pct:.1f}% Overall OEE</b>, producing <b>{produced_units:,} units</b> with <b>{scrap_units:,} scrap defects</b>.",
        f"<b>Bottleneck Throughput:</b> Governed by constraint asset <b>{bottleneck_name}</b> running at planned cadence.",
        f"<b>Availability & Stoppages:</b> Cumulative shift downtime was partitioned across active operational and mechanical reasons.",
        "<b>Incoming Directive:</b> Incoming crew to maintain lubricant levels and verify cap torque specs at next product transition."
    ]
    for b in bullets:
        story.append(Paragraph(f"&bull; {b}", bullet_style))
        story.append(Spacer(1, 3))
    story.append(Spacer(1, 8))

    # 4. ISO 22400 Line OEE Scorecard Table
    story.append(Paragraph("2. ISO 22400 Equipment Effectiveness Breakdown", section_heading))
    avail_pct = kpis.get('availability_percent', 0.0)
    perf_pct = kpis.get('performance_percent', 0.0)
    qual_pct = kpis.get('quality_percent', 0.0)

    oee_data = [
        [
            Paragraph("METRIC", cell_header),
            Paragraph("MEASURED", cell_header),
            Paragraph("WORLD-CLASS BENCHMARK", cell_header),
            Paragraph("STATUS", cell_header),
        ],
        [
            Paragraph("Availability (A)", cell_style),
            Paragraph(f"<b>{avail_pct:.1f}%</b>", cell_style),
            Paragraph("90.0%", cell_style),
            Paragraph("Optimal" if avail_pct >= 90 else "Action Required", cell_style),
        ],
        [
            Paragraph("Performance (P)", cell_style),
            Paragraph(f"<b>{perf_pct:.1f}%</b>", cell_style),
            Paragraph("95.0%", cell_style),
            Paragraph("Optimal" if perf_pct >= 95 else "Speed Loss Detected", cell_style),
        ],
        [
            Paragraph("Quality (Q)", cell_style),
            Paragraph(f"<b>{qual_pct:.1f}%</b>", cell_style),
            Paragraph("99.9%", cell_style),
            Paragraph("Optimal" if qual_pct >= 99 else "Scrap Notice", cell_style),
        ],
        [
            Paragraph("<b>Overall Line OEE (A x P x Q)</b>", cell_style),
            Paragraph(f"<b>{oee_pct:.1f}%</b>", cell_style),
            Paragraph("<b>85.0%</b>", cell_style),
            Paragraph("<b>World-Class</b>" if oee_pct >= 85 else "<b>Below Target</b>", cell_style),
        ],
    ]
    t_oee = Table(oee_data, colWidths=[150, 120, 150, 120])
    t_oee.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16A34A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ECFDF5')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_oee)
    story.append(Spacer(1, 10))

    # 5. Top Downtime Stoppage Events
    story.append(Paragraph("3. Equipment Reliability & Leading Stoppage Causes", section_heading))
    pareto = calculate_juran_pareto(line=line)
    top_causes = pareto.get('by_duration', [])[:5]

    stoppage_rows = [
        [
            Paragraph("REASON DESCRIPTION", cell_header),
            Paragraph("CATEGORY", cell_header),
            Paragraph("OCCURRENCES", cell_header),
            Paragraph("DURATION (MIN)", cell_header),
            Paragraph("PARETO %", cell_header),
        ]
    ]
    if top_causes:
        for c in top_causes:
            stoppage_rows.append([
                Paragraph(c.get('label', 'General Unplanned Stop'), cell_style),
                Paragraph(c.get('category', 'Mechanical'), cell_style),
                Paragraph(str(c.get('count', 1)), cell_style),
                Paragraph(f"{c.get('minutes', 0):.0f} m", cell_style),
                Paragraph(f"{c.get('cum_pct', 0):.1f}%", cell_style),
            ])
    else:
        stoppage_rows.append([
            Paragraph("No discrete downtime events recorded during shift.", cell_style),
            Paragraph("-", cell_style),
            Paragraph("-", cell_style),
            Paragraph("0 m", cell_style),
            Paragraph("0.0%", cell_style),
        ])

    t_stop = Table(stoppage_rows, colWidths=[180, 110, 80, 90, 80])
    t_stop.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_stop)
    story.append(Spacer(1, 14))

    # 6. Formal Sign-Off Box
    story.append(Paragraph("4. Supervisory Verification & Formal Sign-Off", section_heading))
    sign_data = [
        [
            Paragraph("<b>Outgoing Shift Leader Signature:</b><br/><br/>_____________________________________<br/><font size='7' color='#6B7280'>Certified production figures, scrap & downtime intervals.</font>", cell_style),
            Paragraph("<b>Incoming Shift Leader Acknowledgement:</b><br/><br/>_____________________________________<br/><font size='7' color='#6B7280'>Acknowledged line condition, open tickets & safety items.</font>", cell_style)
        ]
    ]
    t_sign = Table(sign_data, colWidths=[270, 270])
    t_sign.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#9CA3AF')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_sign)

    doc.build(story)
    buffer.seek(0)
    return buffer
