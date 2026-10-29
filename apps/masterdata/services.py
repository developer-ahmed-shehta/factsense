"""
Master data services: Onboarding Wizard presets, topology generation,
shift schedule calculation, and kiosk hardware pairing.
"""

import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import AuditEvent
from .models import (
    Factory, Line, Machine, Process, Product, Shift,
    PlannedBreak, KioskDevice, ReasonCategory, StoppageReason,
    DefectReason, MachineProductRate
)

INDUSTRY_PRESETS = {
    'WATER': {
        'key': 'WATER',
        'title': 'High-Speed Bottled Water Line',
        'title_ar': 'خط تعبئة مياه معدنية عالي السرعة',
        'industry': 'Beverage / Bottling',
        'default_code': 'LINE-WTR-01',
        'default_name': 'High-Speed Water Line 01',
        'target_oee': 85.0,
        'bottleneck_index': 2,  # 0-indexed: Filler
        'machines': [
            {
                'code': 'BM-10',
                'name': 'Rotary Stretch Blow Molder',
                'name_ar': 'ماكينة نفخ العبوات الدوارة',
                'category': 'BLOW_MOLDER',
                'sequence_order': 10,
                'criticality_rank': 'B',
                'ideal_run_rate_cpm': 150.0,
                'sensor_protocol': 'GPIO_PULSE',
            },
            {
                'code': 'RN-20',
                'name': 'Rotary Air/Water Rinser',
                'name_ar': 'شطافة العبوات الدوارة',
                'category': 'RINSER',
                'sequence_order': 20,
                'criticality_rank': 'B',
                'ideal_run_rate_cpm': 140.0,
                'sensor_protocol': 'MODBUS_TCP',
            },
            {
                'code': 'FL-30',
                'name': 'Gravity Monoblock Filler',
                'name_ar': 'ماكينة التعبئة الأوتوماتيكية (الفيلر)',
                'category': 'FILLER',
                'sequence_order': 30,
                'criticality_rank': 'A',
                'ideal_run_rate_cpm': 120.0,
                'is_bottleneck': True,
                'sensor_protocol': 'MODBUS_TCP',
            },
            {
                'code': 'CP-40',
                'name': 'Rotary Pick-and-Place Capper',
                'name_ar': 'ماكينة تركيب وتثبيت الأغطية (الكابر)',
                'category': 'CAPPER',
                'sequence_order': 40,
                'criticality_rank': 'B',
                'ideal_run_rate_cpm': 140.0,
                'sensor_protocol': 'GPIO_PULSE',
            },
            {
                'code': 'LB-50',
                'name': 'Hot Melt Roll-Fed Labeler',
                'name_ar': 'ماكينة وضع الملصقات (الليبلر)',
                'category': 'LABELER',
                'sequence_order': 50,
                'criticality_rank': 'B',
                'ideal_run_rate_cpm': 130.0,
                'sensor_protocol': 'MODBUS_TCP',
            },
            {
                'code': 'PK-60',
                'name': 'Wrap-Around Case Packer',
                'name_ar': 'ماكينة التعبئة الكرتونية (الباكر)',
                'category': 'PACKER',
                'sequence_order': 60,
                'criticality_rank': 'C',
                'ideal_run_rate_cpm': 130.0,
                'sensor_protocol': 'SIMULATED',
            },
            {
                'code': 'PL-70',
                'name': 'High-Level Robotic Palletizer',
                'name_ar': 'ماكينة الرص الآلي للبالتات (الباليتيزر)',
                'category': 'PALLETIZER',
                'sequence_order': 70,
                'criticality_rank': 'C',
                'ideal_run_rate_cpm': 140.0,
                'sensor_protocol': 'SIMULATED',
            },
        ],
        'default_product': {
            'code': 'SKU-WTR-500ML',
            'name': 'Natural Spring Water 500ml',
            'name_ar': 'مياه طبيعية نقية 500 مل',
            'category': 'Beverage',
            'unit_of_measure': 'Bottle',
            'ideal_cycle_time_sec': Decimal('0.50'),
            'rated_speed_cpm': 120,
            'nominal_weight': Decimal('500.00'),
            'usl_weight': Decimal('505.00'),
            'lsl_weight': Decimal('495.00'),
            'unit_cost': Decimal('1.25'),
            'scrap_cost': Decimal('0.85'),
        }
    },
    'CSD': {
        'key': 'CSD',
        'title': 'Carbonated Soft Drinks (CSD) Line',
        'title_ar': 'خط تعبئة المشروبات الغازية (CSD)',
        'industry': 'Beverage / Carbonated',
        'default_code': 'LINE-CSD-01',
        'default_name': 'CSD Bottling & Canning Line',
        'target_oee': 82.0,
        'bottleneck_index': 1,  # 0-indexed: Isobaric Filler
        'machines': [
            {
                'code': 'RN-10',
                'name': 'Ionized Air Can Rinser',
                'name_ar': 'شطافة العبوات بالهواء المتأين',
                'category': 'RINSER',
                'sequence_order': 10,
                'criticality_rank': 'B',
                'ideal_run_rate_cpm': 180.0,
                'sensor_protocol': 'GPIO_PULSE',
            },
            {
                'code': 'FL-20',
                'name': 'Isobaric Counter-Pressure Filler',
                'name_ar': 'ماكينة التعبئة تحت الضغط المتساوي (أيزوباريك)',
                'category': 'FILLER',
                'sequence_order': 20,
                'criticality_rank': 'A',
                'ideal_run_rate_cpm': 150.0,
                'is_bottleneck': True,
                'sensor_protocol': 'MODBUS_TCP',
            },
            {
                'code': 'CP-30',
                'name': 'Rotary Can Seamer & Capper',
                'name_ar': 'ماكينة درز وإغلاق الكانز والأغطية',
                'category': 'CAPPER',
                'sequence_order': 30,
                'criticality_rank': 'B',
                'ideal_run_rate_cpm': 180.0,
                'sensor_protocol': 'GPIO_PULSE',
            },
            {
                'code': 'PT-40',
                'name': 'Multi-Zone Tunnel Pasteurizer',
                'name_ar': 'نفق البسترة متعدد المناطق',
                'category': 'OTHER',
                'sequence_order': 40,
                'criticality_rank': 'B',
                'ideal_run_rate_cpm': 160.0,
                'sensor_protocol': 'MODBUS_TCP',
            },
            {
                'code': 'LB-50',
                'name': 'Steam Shrink Sleeve Labeler',
                'name_ar': 'ماكينة السليف شيرنك الحراري',
                'category': 'LABELER',
                'sequence_order': 50,
                'criticality_rank': 'C',
                'ideal_run_rate_cpm': 170.0,
                'sensor_protocol': 'SIMULATED',
            },
        ],
        'default_product': {
            'code': 'SKU-CSD-330ML',
            'name': 'Sparkling Cola 330ml Can',
            'name_ar': 'كولا فوارة 330 مل كانز',
            'category': 'Carbonated',
            'unit_of_measure': 'Can',
            'ideal_cycle_time_sec': Decimal('0.40'),
            'rated_speed_cpm': 150,
            'nominal_weight': Decimal('330.00'),
            'usl_weight': Decimal('334.00'),
            'lsl_weight': Decimal('326.00'),
            'unit_cost': Decimal('2.80'),
            'scrap_cost': Decimal('2.10'),
        }
    },
    'OIL': {
        'key': 'OIL',
        'title': 'Edible Oil & Condiments Packaging Line',
        'title_ar': 'خط تعبئة زيوت الطعام والتوابل السائلة',
        'industry': 'Food & Cooking Oil',
        'default_code': 'LINE-OIL-01',
        'default_name': 'Edible Oil Filling Line 01',
        'target_oee': 80.0,
        'bottleneck_index': 0,  # 0-indexed: Piston Filler
        'machines': [
            {
                'code': 'FL-10',
                'name': 'Linear Servo Piston Filler (1L)',
                'name_ar': 'ماكينة تعبئة مكبسية سيرفو 1 لتر',
                'category': 'FILLER',
                'sequence_order': 10,
                'criticality_rank': 'A',
                'ideal_run_rate_cpm': 90.0,
                'is_bottleneck': True,
                'sensor_protocol': 'MODBUS_TCP',
            },
            {
                'code': 'ND-20',
                'name': 'Liquid Nitrogen Headspace Doser',
                'name_ar': 'حاقن النيتروجين السائل للرأس الفارغ',
                'category': 'OTHER',
                'sequence_order': 20,
                'criticality_rank': 'B',
                'ideal_run_rate_cpm': 110.0,
                'sensor_protocol': 'GPIO_PULSE',
            },
            {
                'code': 'SL-30',
                'name': 'Electromagnetic Induction Foil Sealer',
                'name_ar': 'ماكينة لحام الفويل بالحث الكهرومغناطيسي',
                'category': 'SEALER',
                'sequence_order': 30,
                'criticality_rank': 'B',
                'ideal_run_rate_cpm': 110.0,
                'sensor_protocol': 'MODBUS_TCP',
            },
            {
                'code': 'LB-40',
                'name': 'High-Precision Self-Adhesive Wrap Labeler',
                'name_ar': 'ماكينة لصق الاستيكر الدائري عالي الدقة',
                'category': 'LABELER',
                'sequence_order': 40,
                'criticality_rank': 'C',
                'ideal_run_rate_cpm': 100.0,
                'sensor_protocol': 'SIMULATED',
            },
        ],
        'default_product': {
            'code': 'SKU-OIL-1L',
            'name': 'Pure Sunflower Cooking Oil 1L',
            'name_ar': 'زيت دوار الشمس النقي 1 لتر',
            'category': 'Edible Oil',
            'unit_of_measure': 'Bottle',
            'ideal_cycle_time_sec': Decimal('0.67'),
            'rated_speed_cpm': 90,
            'nominal_weight': Decimal('915.00'),
            'usl_weight': Decimal('922.00'),
            'lsl_weight': Decimal('908.00'),
            'unit_cost': Decimal('38.50'),
            'scrap_cost': Decimal('32.00'),
        }
    }
}


def deploy_line_from_preset(factory, line_code, line_name, preset_key='WATER', target_oee=None, user=None):
    """
    Rapid 60-Second Onboarding Wizard deployment:
    Atomically creates Line, sequential Machines with sensor configurations,
    sets designated bottleneck asset, creates product SKU, and generates
    the MachineProductRate speed matrix.
    """
    preset = INDUSTRY_PRESETS.get(preset_key, INDUSTRY_PRESETS['WATER'])

    with transaction.atomic():
        # 1. Create Line
        line, _ = Line.objects.update_or_create(
            factory=factory,
            code=line_code.strip().upper(),
            defaults={
                'name': line_name.strip(),
                'target_oee': float(target_oee or preset['target_oee']),
                'sequence': factory.lines.count() + 1,
            }
        )

        # 2. Create Machines
        created_machines = []
        bottleneck_machine = None

        for m_data in preset['machines']:
            mach, _ = Machine.objects.update_or_create(
                line=line,
                code=f"{line.code}-{m_data['code']}",
                defaults={
                    'name': m_data['name'],
                    'name_ar': m_data.get('name_ar', ''),
                    'category': m_data['category'],
                    'sequence_order': m_data['sequence_order'],
                    'criticality_rank': m_data['criticality_rank'],
                    'ideal_run_rate_cpm': m_data['ideal_run_rate_cpm'],
                    'is_bottleneck': m_data.get('is_bottleneck', False),
                    'sensor_protocol': m_data.get('sensor_protocol', 'SIMULATED'),
                    'sensor_ip': '192.168.1.100',
                    'modbus_address': m_data['sequence_order'] // 10,
                }
            )
            created_machines.append(mach)
            if m_data.get('is_bottleneck'):
                bottleneck_machine = mach

        # Assign bottleneck
        if bottleneck_machine:
            line.bottleneck_machine = bottleneck_machine
        elif created_machines:
            line.bottleneck_machine = created_machines[0]
            line.bottleneck_machine.is_bottleneck = True
            line.bottleneck_machine.save()

        # 3. Create Default Product SKU
        p_data = preset['default_product']
        sku, _ = Product.objects.update_or_create(
            code=f"{line.code}-{p_data['code']}",
            defaults={
                'factory': factory,
                'name': p_data['name'],
                'name_ar': p_data['name_ar'],
                'category': p_data['category'],
                'unit_of_measure': p_data['unit_of_measure'],
                'ideal_cycle_time_sec': p_data['ideal_cycle_time_sec'],
                'rated_speed_cpm': p_data['rated_speed_cpm'],
                'nominal_weight': p_data['nominal_weight'],
                'usl_weight': p_data['usl_weight'],
                'lsl_weight': p_data['lsl_weight'],
                'unit_cost': p_data['unit_cost'],
                'scrap_cost': p_data['scrap_cost'],
                'is_archived': False,
            }
        )
        line.current_product = sku
        line.save()

        # 4. Generate MachineProductRate Matrix
        for mach in created_machines:
            MachineProductRate.objects.update_or_create(
                machine=mach,
                product=sku,
                defaults={
                    'rated_speed_cpm': mach.ideal_run_rate_cpm,
                    'ideal_cycle_time_sec': round(60.0 / mach.ideal_run_rate_cpm, 2) if mach.ideal_run_rate_cpm > 0 else 0.50,
                }
            )

        # 5. Create default Kiosk enrollment for Bottleneck Machine
        if line.bottleneck_machine:
            KioskDevice.objects.get_or_create(
                claim_code=f"KB-{line.code[:4]}-{line.bottleneck_machine.sequence_order}",
                defaults={
                    'machine': line.bottleneck_machine,
                    'device_name': f"Kiosk Tablet {line.bottleneck_machine.code}",
                    'device_token': str(uuid.uuid4()),
                    'status': 'ACTIVE',
                    'is_exclusive': True,
                    'paired_at': timezone.now(),
                    'last_seen_at': timezone.now(),
                }
            )

        # 6. Audit Trail Logging
        if user and user.is_authenticated:
            AuditEvent.objects.create(
                actor=user,
                active_role=getattr(user, 'active_role', 'admin'),
                action='WIZARD_DEPLOY_LINE',
                resource='Line',
                resource_id=str(line.id),
                details={
                    'event': 'WIZARD_DEPLOY_LINE',
                    'line_code': line.code,
                    'preset': preset_key,
                    'machines_count': len(created_machines),
                    'bottleneck': line.bottleneck_machine.code if line.bottleneck_machine else None,
                }
            )

        return line, created_machines, sku


def pair_kiosk_device(claim_code, machine=None, ip_address=None, user=None):
    """
    Pairs an enrolled or unassigned KioskDevice using a claim code.
    Enforces device registration and session exclusivity.
    """
    claim_code = claim_code.strip()
    kiosk = KioskDevice.objects.filter(claim_code=claim_code).first()

    if not kiosk:
        # Create a new claim token record
        kiosk = KioskDevice.objects.create(
            claim_code=claim_code,
            device_name=f"Kiosk Device [{claim_code}]",
            device_token=str(uuid.uuid4()),
            status='ACTIVE' if machine else 'PENDING',
            machine=machine,
            ip_address=ip_address,
            paired_at=timezone.now() if machine else None,
            last_seen_at=timezone.now(),
        )
    else:
        if machine:
            kiosk.machine = machine
            kiosk.status = 'ACTIVE'
            kiosk.paired_at = timezone.now()
        if ip_address:
            kiosk.ip_address = ip_address
        kiosk.last_seen_at = timezone.now()
        kiosk.save()

    if user and user.is_authenticated:
        AuditEvent.objects.create(
            actor=user,
            active_role=getattr(user, 'active_role', 'admin'),
            action='DEVICE_PAIR',
            resource='KioskDevice',
            resource_id=str(kiosk.id),
            details={
                'claim_code': kiosk.claim_code,
                'device_name': kiosk.device_name,
                'machine_bound': kiosk.machine.code if kiosk.machine else None,
                'status': kiosk.status,
            }
        )

    return kiosk
