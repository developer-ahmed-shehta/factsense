"""
Django management command to seed all 10 canonical roles, plant master data,
processes, exact reference screenshot products, and development demo users.
"""

from decimal import Decimal
from datetime import time
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import Role, UserRoleAssignment
from apps.masterdata.models import (
    Factory, Line, Machine, Process, Product, Shift,
    PlannedBreak, KioskDevice, ReasonCategory, StoppageReason,
    DefectReason, MachineProductRate
)

User = get_user_model()

DEFAULT_PASSWORD = "Factsense@2026"

CANONICAL_ROLES = [
    {
        'code': 'planner',
        'name': 'Production Planner',
        'name_ar': 'مخطط إنتاج',
        'default_landing': '/planning/products/',
        'description': 'Master data and planning. Product SKUs, process routes, benchmark speed matrix, shift schedules.',
        'sequence': 10,
    },
    {
        'code': 'operator',
        'name': 'Line Operator',
        'name_ar': 'مشغل ماكينة',
        'default_landing': '/operator/',
        'description': 'Shop-floor machine operator. Production logging, scrap counting, downtime classification.',
        'sequence': 20,
    },
    {
        'code': 'supervisor',
        'name': 'Shift Supervisor',
        'name_ar': 'مشرف وردية',
        'default_landing': '/floor/',
        'description': 'Production shift leader. Floor overview, stoppage splitting, SMED tracking, shift handover.',
        'sequence': 30,
    },
    {
        'code': 'maintenance',
        'name': 'Maintenance Technician',
        'name_ar': 'فني صيانة',
        'default_landing': '/maintenance/',
        'description': 'Maintenance technician. Breakdown response, repair clock-in, spares, machine release.',
        'sequence': 40,
    },
    {
        'code': 'quality',
        'name': 'Quality Specialist',
        'name_ar': 'أخصائي جودة',
        'default_landing': '/quality/',
        'description': 'Quality assurance. ISO 22400-2 SPC charts, weight samples, defect logs, giveaway simulator.',
        'sequence': 50,
    },
    {
        'code': 'supply_chain',
        'name': 'Supply Chain Officer',
        'name_ar': 'مسؤول سلاسل الإمداد',
        'default_landing': '/work-orders/',
        'description': 'Supply chain and ERP sync. Work orders, staging progress, material delivery.',
        'sequence': 70,
    },
    {
        'code': 'manager',
        'name': 'Plant Director',
        'name_ar': 'مدير المصنع',
        'default_landing': '/dashboard/',
        'description': 'Plant management. Executive OEE, TPM Six Big Losses, financial downtime costs, benchmarking.',
        'sequence': 80,
    },
    {
        'code': 'admin',
        'name': 'System Administrator',
        'name_ar': 'مسؤول النظام',
        'default_landing': '/administration/',
        'description': 'System administration. User management, scoped roles, IoT gateway onboarding, audit logs.',
        'sequence': 90,
    },
    {
        'code': 'controller',
        'name': 'Simulator Controller',
        'name_ar': 'مسؤول المحاكاة',
        'default_landing': '/controller/',
        'description': 'Simulation and demo master. Telemetry generation, scenario injection, clock multiplier.',
        'sequence': 100,
    },
]


class Command(BaseCommand):
    help = "Seed all 10 canonical roles, plant hierarchy, reference screenshot products, and demo users."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(">>> Initializing FactSense Master Data & Demo Users..."))

        # 1. Seed Roles
        role_objs = {}
        for role_data in CANONICAL_ROLES:
            role, created = Role.objects.update_or_create(
                code=role_data['code'],
                defaults=role_data
            )
            role_objs[role.code] = role

        # 2. Seed Factory & Plant Hierarchy
        factory, _ = Factory.objects.update_or_create(
            code="CAIRO-PLANT-01",
            defaults={
                'name': "Cairo Bottling Facility",
                'name_ar': "مصنع تعبئة القاهرة",
                'location': "6th of October Industrial City, Giza",
                'industry': "Industrial Manufacturing",
                'timezone': "Africa/Cairo",
                'currency': "EGP",
                'is_active': True,
            }
        )

        line1, _ = Line.objects.update_or_create(
            factory=factory,
            code="LINE-01",
            defaults={
                'name': "Machining & Assembly Line 1",
                'name_ar': "خط التشغيل والتجميع 1",
                'sequence': 1,
                'target_oee': 85.0,
            }
        )

        # Machines
        machines_data = [
            ('CNC-01', 'CNC Turning Machine 01', 'ماكينة خراطة CNC 01', 'FILLER', 10, 'A', 120.0, True),
            ('ML-01', 'CNC Milling Center 01', 'مركز تفريز CNC 01', 'BLOW_MOLDER', 20, 'B', 140.0, False),
            ('DR-01', 'Radial Drill 01', 'ماكينة ثقب شعاعية 01', 'RINSER', 30, 'C', 150.0, False),
            ('GR-01', 'Surface Grinder 01', 'ماكينة تجليخ سطوح 01', 'LABELER', 40, 'B', 130.0, False),
        ]
        machine_objs = {}
        for code, name, name_ar, cat, seq, rank, cpm, is_bn in machines_data:
            mach, _ = Machine.objects.update_or_create(
                line=line1,
                code=code,
                defaults={
                    'name': name,
                    'name_ar': name_ar,
                    'category': cat,
                    'sequence_order': seq,
                    'criticality_rank': rank,
                    'ideal_run_rate_cpm': cpm,
                    'is_bottleneck': is_bn,
                }
            )
            machine_objs[code] = mach

        line1.bottleneck_machine = machine_objs['CNC-01']
        line1.save()

        # 3. Seed Shifts
        shifts_data = [
            ('SHIFT-M', 'Morning Shift', 'الوردية الصباحية', time(7, 0), time(15, 0), 30, 1),
            ('SHIFT-E', 'Evening Shift', 'الوردية المسائية', time(15, 0), time(23, 0), 30, 2),
            ('SHIFT-N', 'Night Shift', 'الوردية الليلية', time(23, 0), time(7, 0), 30, 3),
        ]
        shift_objs = {}
        for scode, sname, sname_ar, st, et, ub, sseq in shifts_data:
            s_obj, _ = Shift.objects.update_or_create(
                factory=factory,
                code=scode,
                defaults={
                    'name': sname,
                    'name_ar': sname_ar,
                    'start_time': st,
                    'end_time': et,
                    'unpaid_break_minutes': ub,
                    'sequence': sseq,
                }
            )
            shift_objs[scode] = s_obj

        # Seed Planned Breaks for Morning Shift
        PlannedBreak.objects.get_or_create(
            shift=shift_objs['SHIFT-M'],
            name='Morning Tea Break',
            defaults={
                'name_ar': 'استراحة الشاي الصباحية',
                'start_time': time(9, 30),
                'end_time': time(9, 45),
                'duration_minutes': 15,
                'is_unpaid': True,
            }
        )
        PlannedBreak.objects.get_or_create(
            shift=shift_objs['SHIFT-M'],
            name='Lunch & Prayer Break',
            defaults={
                'name_ar': 'استراحة الغداء والصلاة',
                'start_time': time(12, 30),
                'end_time': time(13, 0),
                'duration_minutes': 30,
                'is_unpaid': True,
            }
        )

        # 4. Seed Processes matching the Reference Screenshot
        processes_data = [
            ('P1', 'خراطة مرحلة أولى', 'خراطة مرحلة أولى', 1),
            ('P2', 'خراطة مرحلة ثانية', 'خراطة مرحلة ثانية', 2),
            ('P3', 'تسعير', 'تسعير', 3),
            ('P4', 'بورنج', 'بورنج', 4),
            ('P5', 'خراطة', 'خراطة', 5),
            ('P6', 'تخريم', 'تخريم', 6),
            ('P7', 'تجميع', 'تجميع', 7),
        ]
        process_objs = {}
        for pcode, pname, pname_ar, pseq in processes_data:
            p, _ = Process.objects.update_or_create(
                code=pcode,
                defaults={'name': pname, 'name_ar': pname_ar, 'sequence_order': pseq}
            )
            process_objs[pcode] = p

        # 5. Seed Exact Products from Reference Screenshot
        screenshot_products = [
            {
                'code': 'WSHTS862',
                'name': 'Butterfly 7500-1000-10 - عمود استانلس (316) لامع قطر 110*348 مم خلفى تام التشغيل',
                'name_ar': 'Butterfly 7500-1000-10 - عمود استانلس (316) لامع قطر 110*348 مم خلفى تام التشغيل',
                'category': 'Butterfly Shafts',
                'unit_of_measure': '-',
                'sop_document_title': 'View Design',
                'sop_document_url': '#',
                'ideal_cycle_time_sec': Decimal('0.00'),
                'rated_speed_cpm': 0,
                'procs': ['P1', 'P2'],
            },
            {
                'code': 'WSHTS863',
                'name': 'Butterfly 7500-1000-10 - عمود استانلس (316) لامع قطر 110*618 مم امامى تام التشغيل',
                'name_ar': 'Butterfly 7500-1000-10 - عمود استانلس (316) لامع قطر 110*618 مم امامى تام التشغيل',
                'category': 'Butterfly Shafts',
                'unit_of_measure': '-',
                'sop_document_title': 'View Design',
                'sop_document_url': '#',
                'ideal_cycle_time_sec': Decimal('0.00'),
                'rated_speed_cpm': 0,
                'procs': ['P1', 'P2'],
            },
            {
                'code': 'MVNLSC1500005C/WA',
                'name': 'تشغيل/جلبة -16-1500-7800 Pull',
                'name_ar': 'تشغيل/جلبة -16-1500-7800 Pull',
                'category': 'Pull Bushings',
                'unit_of_measure': '-',
                'sop_document_title': 'View Design',
                'sop_document_url': '#',
                'ideal_cycle_time_sec': Decimal('0.00'),
                'rated_speed_cpm': 0,
                'procs': ['P1', 'P2', 'P3'],
            },
            {
                'code': 'WSHTS226',
                'name': 'تام التشغيل -16-600-7800-Plug- عمود استانلس (420) لامع قطر 75 مم طول 200 خلفى',
                'name_ar': 'تام التشغيل -16-600-7800-Plug- عمود استانلس (420) لامع قطر 75 مم طول 200 خلفى',
                'category': 'Plug Shafts',
                'unit_of_measure': '-',
                'sop_document_title': 'View Design',
                'sop_document_url': '#',
                'ideal_cycle_time_sec': Decimal('0.00'),
                'rated_speed_cpm': 0,
                'procs': ['P1', 'P2'],
            },
            {
                'code': 'WMRM028',
                'name': 'قطر ترس 70 مم - طول 258 مم -S40R31 بنيون مناول رئيسى',
                'name_ar': 'قطر ترس 70 مم - طول 258 مم -S40R31 بنيون مناول رئيسى',
                'category': 'Pinion Gears',
                'unit_of_measure': '-',
                'sop_document_title': 'View Design',
                'sop_document_url': '#',
                'ideal_cycle_time_sec': Decimal('0.00'),
                'rated_speed_cpm': 0,
                'procs': ['P1', 'P2'],
            },
            {
                'code': 'WSHTS903',
                'name': 'Butterfly 7500-400-16 عمود استانلس (420) قطر 50*339 مم امامى',
                'name_ar': 'Butterfly 7500-400-16 عمود استانلس (420) قطر 50*339 مم امامى',
                'category': 'Butterfly Shafts',
                'unit_of_measure': '-',
                'sop_document_title': 'View Design',
                'sop_document_url': '#',
                'ideal_cycle_time_sec': Decimal('0.00'),
                'rated_speed_cpm': 0,
                'procs': ['P1', 'P2'],
            },
            {
                'code': 'WMRM013',
                'name': 'قطر ترس 45- طول 241 مم -560R12 بنيون طارة',
                'name_ar': 'قطر ترس 45- طول 241 مم -560R12 بنيون طارة',
                'category': 'Pinion Gears',
                'unit_of_measure': '-',
                'sop_document_title': 'View Design',
                'sop_document_url': '#',
                'ideal_cycle_time_sec': Decimal('0.00'),
                'rated_speed_cpm': 0,
                'procs': ['P1', 'P2'],
            },
            {
                'code': 'MVNLDC0800005C/W1',
                'name': 'تشغيل/ديسك -10-800-7800 Pull',
                'name_ar': 'تشغيل/ديسك -10-800-7800 Pull',
                'category': 'Discs',
                'unit_of_measure': '-',
                'sop_document_title': 'View Design',
                'sop_document_url': '#',
                'ideal_cycle_time_sec': Decimal('0.00'),
                'rated_speed_cpm': 0,
                'procs': ['P1', 'P2', 'P4'],
            },
            {
                'code': 'MVNLPC0800005C/W1',
                'name': 'تشغيل/جسم 10-800-7800 Pull',
                'name_ar': 'تشغيل/جسم 10-800-7800 Pull',
                'category': 'Bodies',
                'unit_of_measure': '-',
                'sop_document_title': 'View Design',
                'sop_document_url': '#',
                'ideal_cycle_time_sec': Decimal('0.00'),
                'rated_speed_cpm': 0,
                'procs': ['P1', 'P2', 'P4'],
            },
            {
                'code': 'WSHTS241',
                'name': 'طول 286 مم - تام التشغيل 10-900-7800-Plug- عمود استانلس (420) لامع قطر 110 مم خلفى',
                'name_ar': 'طول 286 مم - تام التشغيل 10-900-7800-Plug- عمود استانلس (420) لامع قطر 110 مم خلفى',
                'category': 'Plug Shafts',
                'unit_of_measure': '-',
                'sop_document_title': 'View Design',
                'sop_document_url': '#',
                'ideal_cycle_time_sec': Decimal('0.00'),
                'rated_speed_cpm': 0,
                'procs': ['P1', 'P2'],
            },
            {
                'code': 'WSHTS248',
                'name': 'طول 511 مم - تام التشغيل 10-900-7800-Plug- عمود استانلس (420) لامع قطر 110 مم امامى',
                'name_ar': 'طول 511 مم - تام التشغيل 10-900-7800-Plug- عمود استانلس (420) لامع قطر 110 مم امامى',
                'category': 'Plug Shafts',
                'unit_of_measure': '-',
                'sop_document_title': 'View Design',
                'sop_document_url': '#',
                'ideal_cycle_time_sec': Decimal('0.00'),
                'rated_speed_cpm': 0,
                'procs': ['P1', 'P2'],
            },
            {
                'code': 'MVB5D11200005C/W1',
                'name': 'Butterfly 7500-1200-10 تشغيل/ديسك',
                'name_ar': 'Butterfly 7500-1200-10 تشغيل/ديسك',
                'category': 'Discs',
                'unit_of_measure': '-',
                'sop_document_title': 'View Design',
                'sop_document_url': '#',
                'ideal_cycle_time_sec': Decimal('0.00'),
                'rated_speed_cpm': 0,
                'procs': ['P5', 'P6'],
            },
        ]

        # Clear old demo products and insert exact screenshot products
        Product.objects.all().delete()
        for pdata in screenshot_products:
            procs = pdata.pop('procs')
            prod = Product.objects.create(
                factory=factory,
                code=pdata['code'],
                name=pdata['name'],
                name_ar=pdata['name_ar'],
                category=pdata['category'],
                unit_of_measure=pdata['unit_of_measure'],
                sop_document_title=pdata['sop_document_title'],
                sop_document_url=pdata['sop_document_url'],
                ideal_cycle_time_sec=pdata['ideal_cycle_time_sec'],
                rated_speed_cpm=pdata['rated_speed_cpm'],
            )
            prod.processes.set([process_objs[pk] for pk in procs if pk in process_objs])

        # 6. Seed MachineProductRate Matrix
        sample_prods = list(Product.objects.all()[:3])
        for mach in machine_objs.values():
            for p in sample_prods:
                MachineProductRate.objects.update_or_create(
                    machine=mach,
                    product=p,
                    defaults={
                        'rated_speed_cpm': mach.ideal_run_rate_cpm,
                        'ideal_cycle_time_sec': round(60.0 / mach.ideal_run_rate_cpm, 2) if mach.ideal_run_rate_cpm > 0 else 0.50
                    }
                )

        # 7. Seed Stoppage & Defect Reason Taxonomies
        cat_mech, _ = ReasonCategory.objects.get_or_create(
            name='Mechanical Failure',
            defaults={'name_ar': 'أعطال ميكانيكية', 'department': 'MECHANICAL', 'sequence': 10}
        )
        cat_elec, _ = ReasonCategory.objects.get_or_create(
            name='Electrical & Controls',
            defaults={'name_ar': 'أعطال كهربائية وتحكم', 'department': 'ELECTRICAL', 'sequence': 20}
        )
        cat_ops, _ = ReasonCategory.objects.get_or_create(
            name='Operational & Setup',
            defaults={'name_ar': 'تشغيل وضبط', 'department': 'OPERATIONS', 'sequence': 30}
        )
        cat_qual, _ = ReasonCategory.objects.get_or_create(
            name='Quality & Materials',
            defaults={'name_ar': 'جودة وخامات', 'department': 'QUALITY', 'sequence': 40}
        )

        stoppage_reasons = [
            (cat_mech, 'MECH_JAM', 'Mechanical Jam / Misfeed', 'انحشار ميكانيكي', 'AVAILABILITY_BREAKDOWN', False, False, 20),
            (cat_mech, 'BEARING_FAIL', 'Spindle Bearing Overheat', 'سخونة رولمان بلي العمود', 'AVAILABILITY_BREAKDOWN', False, True, 45),
            (cat_elec, 'SENSOR_FAULT', 'Photoelectric Sensor Failure', 'عطل حساس الخلايا الضوئية', 'AVAILABILITY_BREAKDOWN', False, False, 15),
            (cat_elec, 'POWER_DIP', 'Inverter Drive Trip', 'فصل مغير السرعة إنفرتر', 'AVAILABILITY_BREAKDOWN', False, False, 10),
            (cat_ops, 'CHANGEOVER', 'Mold & Tooling Changeover', 'تغيير الاسطمبة والعدة', 'AVAILABILITY_CHANGEOVER', True, False, 40),
            (cat_ops, 'CLEANING', 'Sanitation & Line CIP Cycle', 'تنظيف وغسيل الخط', 'AVAILABILITY_CHANGEOVER', True, False, 30),
            (cat_ops, 'NO_MATERIAL', 'Material Hopper Starvation', 'نفاد الخام من القادوس', 'PERFORMANCE_MINOR_STOP', False, False, 5),
            (cat_qual, 'SEAL_DEFECT', 'Cap Seal Misalignment', 'خلل إحكام غلق الغطاء', 'QUALITY_DEFECTS', False, False, 15),
            (cat_qual, 'STARTUP_SCRAP', 'Thermal Stabilization Rejects', 'هالك بدء التشغيل الحراري', 'QUALITY_STARTUP_SCRAP', True, False, 10),
        ]
        for cat, rcode, rname, rname_ar, tpm, is_pl, force_lg, res_min in stoppage_reasons:
            StoppageReason.objects.update_or_create(
                code=rcode,
                defaults={
                    'category': cat,
                    'name': rname,
                    'name_ar': rname_ar,
                    'tpm_loss_type': tpm,
                    'is_planned': is_pl,
                    'force_logout': force_lg,
                    'standard_resolution_min': res_min,
                }
            )

        defect_reasons = [
            ('DEF_DENT', 'Container Dent / Deformation', 'انبعاج أو تشوه العبوة', 'Packaging', 'SCRAP'),
            ('DEF_FILL', 'Underfill / Short Volume Level', 'نقص منسوب التعبئة', 'Filling', 'REWORK'),
            ('DEF_LEAK', 'Cap Leak / Torque Failure', 'تسريب الغطاء أو عزم ربط غير كاف', 'Capping', 'QUARANTINE'),
            ('DEF_LABEL', 'Misaligned / Torn Label', 'ملصق مائل أو ممزق', 'Labeling', 'REWORK'),
        ]
        for dcode, dname, dname_ar, dcat, ddisp in defect_reasons:
            DefectReason.objects.update_or_create(
                code=dcode,
                defaults={
                    'name': dname,
                    'name_ar': dname_ar,
                    'category': dcat,
                    'default_disposition': ddisp,
                }
            )

        # 8. Seed Kiosk Devices
        from django.utils import timezone
        KioskDevice.objects.update_or_create(
            claim_code='FL01-8842',
            defaults={
                'machine': machine_objs['CNC-01'],
                'device_name': 'Operator Tablet FL-01',
                'device_token': 'f7d2948a-1122-3344-5566-778899aabbcc',
                'ip_address': '192.168.1.101',
                'mac_address': '00:1A:2B:3C:4D:5E',
                'status': 'ACTIVE',
                'is_exclusive': True,
                'paired_at': timezone.now(),
                'last_seen_at': timezone.now(),
            }
        )
        KioskDevice.objects.update_or_create(
            claim_code='MOXA-2026',
            defaults={
                'machine': None,
                'device_name': 'Edge Gateway Moxa 01',
                'device_token': 'e5c1827b-9988-7766-5544-332211ddeeff',
                'ip_address': '192.168.1.50',
                'mac_address': 'B8:27:EB:12:34:56',
                'status': 'PENDING',
                'is_exclusive': False,
            }
        )

        # 9. Seed Demo Users
        demo_users_specs = [
            ('planner_demo', 'Nourhan Adel', 'نورهان عادل', 'planner@factsense.local', 'planner', None, None),
            ('operator_demo', 'Ahmed Hassan', 'أحمد حسن', 'operator@factsense.local', 'operator', machine_objs['CNC-01'], line1),
            ('supervisor_demo', 'Mahmoud El-Sayed', 'محمود السيد', 'supervisor@factsense.local', 'supervisor', None, line1),
            ('maintenance_demo', 'Tariq Mansour', 'طارق منصور', 'maintenance@factsense.local', 'maintenance', None, None),
            ('quality_demo', 'Kareem Mostafa', 'كريم مصطفى', 'quality@factsense.local', 'quality', None, None),
            ('supply_demo', 'Omar Farouk', 'عمر فاروق', 'supply@factsense.local', 'supply_chain', None, None),
            ('manager_demo', 'Hazem Barakat', 'حازم بركات', 'manager@factsense.local', 'manager', None, None),
            ('admin_demo', 'System Administrator', 'مسؤول النظام', 'admin@factsense.local', 'admin', None, None),
            ('controller_demo', 'Simulation Controller', 'مسؤول المحاكاة', 'demo@factsense.local', 'controller', None, None),
        ]

        for uname, full_name, ar_name, email, rcode, mach, line in demo_users_specs:
            names = full_name.split(' ', 1)
            first_name = names[0]
            last_name = names[1] if len(names) > 1 else ''
            is_admin = (rcode == 'admin')

            user, _ = User.objects.update_or_create(
                username=uname,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'arabic_name': ar_name,
                    'email': email,
                    'is_staff': is_admin,
                    'is_superuser': is_admin,
                    'preferred_language': 'en',
                    'theme': 'light',
                }
            )
            user.set_password(DEFAULT_PASSWORD)
            user.save()

            UserRoleAssignment.objects.update_or_create(
                user=user,
                role=role_objs[rcode],
                defaults={
                    'factory': factory if rcode != 'controller' else None,
                    'line': line,
                    'machine': mach,
                    'is_active': True,
                }
            )

        # Multi-role users
        lead_tech, _ = User.objects.update_or_create(
            username='lead_tech',
            defaults={
                'first_name': 'Khaled',
                'last_name': 'Ibrahim',
                'arabic_name': 'خالد إبراهيم',
                'email': 'lead_tech@factsense.local',
                'preferred_language': 'en',
            }
        )
        lead_tech.set_password(DEFAULT_PASSWORD)
        lead_tech.save()
        UserRoleAssignment.objects.update_or_create(
            user=lead_tech, role=role_objs['supervisor'], defaults={'factory': factory, 'line': line1, 'is_active': True}
        )
        UserRoleAssignment.objects.update_or_create(
            user=lead_tech, role=role_objs['maintenance'], defaults={'factory': factory, 'is_active': True}
        )

        ops_manager, _ = User.objects.update_or_create(
            username='ops_manager',
            defaults={
                'first_name': 'Tarek',
                'last_name': 'Kamel',
                'arabic_name': 'طارق كامل',
                'email': 'ops_manager@factsense.local',
                'preferred_language': 'en',
            }
        )
        ops_manager.set_password(DEFAULT_PASSWORD)
        ops_manager.save()
        UserRoleAssignment.objects.update_or_create(
            user=ops_manager, role=role_objs['manager'], defaults={'factory': factory, 'is_active': True}
        )
        UserRoleAssignment.objects.update_or_create(
            user=ops_manager, role=role_objs['planner'], defaults={'factory': factory, 'is_active': True}
        )

        # Cleanup removed engineer role and demo user if present in database
        User.objects.filter(username__in=['engineer_demo', 'dual_eng']).delete()
        Role.objects.filter(code='engineer').delete()

        # Seed sample spare parts for Maintenance Kanban
        from apps.operations.models import SparePart, MaintenanceTicket
        from apps.alerts.models import AlertRule, AlertIncident
        from apps.quality.models import SPCConfig, QualitySubgroup, QualitySample
        from apps.quality.services.spc_service import record_weight_samples_and_subgroup

        spares_data = [
            ('SP-MEC-01', 'Rotary Capping Chuck Spring', 'زنبرك رأس التغطية الدوار', 'MECHANICAL', 12, 3, Decimal('75.00'), 'Bin A-02'),
            ('SP-ELE-02', 'Photoelectric Pulse Sensor 24V', 'حساس عد النبضات الضوئي', 'ELECTRICAL', 8, 2, Decimal('450.00'), 'Bin B-05'),
            ('SP-PNE-03', '5/2 Way Solenoid Valve (Festo)', 'صمام هواء كهربائي خماسي', 'PNEUMATIC', 4, 1, Decimal('320.00'), 'Bin C-01'),
            ('SP-MEC-04', 'Infeed Starwheel Guide Set', 'طقم موجهات النجمة الدوارة', 'TOOLING', 2, 1, Decimal('1200.00'), 'Bin T-12'),
            ('SP-CON-05', 'Food-Grade Silicone Seal 40mm', 'حلقات سيليكون عازلة غذائية', 'CONSUMABLE', 25, 5, Decimal('35.00'), 'Bin S-03'),
        ]
        for pnum, pname, par_name, pcat, pstock, pmin, pcost, ploc in spares_data:
            SparePart.objects.update_or_create(
                part_number=pnum,
                defaults={
                    'factory': factory,
                    'name': pname,
                    'name_ar': par_name,
                    'category': pcat,
                    'in_stock_quantity': pstock,
                    'min_stock_level': pmin,
                    'unit_cost': pcost,
                    'storage_location': ploc,
                }
            )

        # Seed an initial open maintenance ticket on line 1 capper
        capper_mach = Machine.objects.filter(line=line1, category='CAPPER').first()
        if capper_mach:
            MaintenanceTicket.objects.get_or_create(
                ticket_number='TKT-2026-M001',
                defaults={
                    'machine': capper_mach,
                    'line': line1,
                    'shift': factory.shifts.first(),
                    'title': 'Cap Chute Jam and Chuck Spring Wear',
                    'description': 'Frequent bottle capping jams reported during morning run. Spring tension loose.',
                    'priority': 'HIGH',
                    'status': 'OPEN',
                    'reported_by': User.objects.filter(username='operator_demo').first(),
                    'force_lockout': False,
                }
            )

        # Seed Configurable Alert Rules (Batch 5 - F08)
        rules_data = [
            ('Excessive Continuous Downtime > 15m', 'توقف تشغيلي مطول يتجاوز 15 دقيقة', 'GLOBAL', 'DOWNTIME_DURATION', 'CRITICAL', Decimal('15.0'), 900, 10),
            ('Low Operating Speed (< 80% Rated)', 'انخفاض سرعة التشغيل عن 80% من المقرر', 'GLOBAL', 'LOW_SPEED', 'WARNING', Decimal('80.0'), 300, 5),
            ('High Temperature Overheat > 75C', 'ارتفاع حرارة المحرك عن 75 م°', 'GLOBAL', 'TEMPERATURE_HIGH', 'CRITICAL', Decimal('75.0'), 180, 10),
            ('Excessive Vibration RMS > 4.5 mm/s', 'اهتزاز ميكانيكي مفرط يتجاوز 4.5 مم/ث', 'GLOBAL', 'VIBRATION_HIGH', 'WARNING', Decimal('4.5'), 180, 10),
            ('Consecutive Weight Out of Spec', 'انحراف وزني متتالي خارج حدود المواصفة', 'GLOBAL', 'WEIGHT_OUT_OF_SPEC', 'WARNING', Decimal('2.0'), 120, 15),
        ]
        for rname, rname_ar, rscope, rtype, rsev, rthresh, rdur, rcool in rules_data:
            AlertRule.objects.update_or_create(
                name=rname,
                defaults={
                    'name_ar': rname_ar,
                    'scope': rscope,
                    'rule_type': rtype,
                    'severity': rsev,
                    'threshold_value': rthresh,
                    'duration_seconds': rdur,
                    'cooldown_minutes': rcool,
                    'auto_resolve': True,
                    'is_active': True,
                }
            )

        # Seed Quality SPC Subgroups & Samples (Batch 5 - F07)
        filler_mach = Machine.objects.filter(line=line1, category='FILLER').first() or Machine.objects.filter(line=line1).first()
        prod_water = Product.objects.filter(code__icontains='WTR').first() or Product.objects.first()
        if filler_mach and prod_water:
            # Seed 5 consecutive subgroups of 5 samples around 501.2g (+1.2g overfill drift)
            subgroup_batches = [
                [501.20, 501.50, 500.90, 501.30, 501.10],
                [501.40, 501.80, 501.00, 501.50, 501.30],
                [500.80, 501.20, 501.10, 501.60, 501.30],
                [501.50, 502.10, 501.40, 501.90, 501.10],
                [501.10, 501.40, 500.95, 501.35, 501.20],
                [501.30, 501.70, 501.05, 501.45, 501.50],
            ]
            op_user = User.objects.filter(username='operator_demo').first()
            for b in subgroup_batches:
                record_weight_samples_and_subgroup(
                    machine=filler_mach,
                    product=prod_water,
                    weights=b,
                    operator=op_user,
                    line=line1,
                    is_simulated=False
                )

        # Seed Planning & Work Orders (Batch 6 - F18)
        from apps.planning.models import WorkOrder, MaterialDelivery, ERPSyncRun
        from apps.planning.services.work_order_service import (
            create_work_order, release_work_order, start_work_order,
            stage_material, assign_shift_schedule
        )
        from apps.planning.services.erp_service import simulate_erp_pull
        import datetime

        planner_user = User.objects.filter(username='planner_demo').first()
        now = timezone.now()
        today = now.date()

        if prod_water and line1:
            # 1. Active Work Order in Progress
            wo1 = WorkOrder.objects.filter(order_number='WO-2026-001').first()
            if not wo1:
                wo1 = create_work_order(
                    order_number='WO-2026-001',
                    product_id=prod_water.id,
                    line_id=line1.id,
                    target_quantity=25000,
                    planned_start=now - datetime.timedelta(hours=4),
                    planned_end=now + datetime.timedelta(hours=4),
                    priority='HIGH',
                    lot_number='LOT-WTR-20261029-A',
                    notes='High-priority retail fulfillment batch for Carrefour KSA.',
                    created_by=planner_user
                )
                release_work_order(wo1, user=planner_user)
                start_work_order(wo1, user=planner_user)
                wo1.produced_quantity = 14200
                wo1.scrap_quantity = 210
                wo1.save()

                # Stage materials on wo1
                for mat in wo1.materials.all():
                    stage_material(mat, mat.required_quantity, lot_number=f"LOT-SUPP-{(mat.material_code[-3:] if len(mat.material_code) >= 3 else '101')}", user=planner_user)

                # Schedule on morning shift
                shift1 = factory.shifts.first()
                if shift1:
                    assign_shift_schedule(wo1, shift1, today, target_units=15000, user=planner_user)

            # 2. Work Order Released to Floor
            wo2 = WorkOrder.objects.filter(order_number='WO-2026-002').first()
            if not wo2:
                wo2 = create_work_order(
                    order_number='WO-2026-002',
                    product_id=prod_water.id,
                    line_id=line1.id,
                    target_quantity=18000,
                    planned_start=now + datetime.timedelta(hours=4),
                    planned_end=now + datetime.timedelta(hours=12),
                    priority='NORMAL',
                    lot_number='LOT-WTR-20261029-B',
                    notes='Afternoon run scheduled following CIP cleaning.',
                    created_by=planner_user
                )
                release_work_order(wo2, user=planner_user)
                for mat in wo2.materials.all()[:2]:
                    stage_material(mat, mat.required_quantity * Decimal('0.5'), lot_number="LOT-SUPP-PARTIAL", user=planner_user)

            # 3. Simulate Inbound ERP pull with conflict
            if not ERPSyncRun.objects.exists():
                simulate_erp_pull(user=planner_user, force_conflict=True)

            # 4. Inbound Delivery
            if not MaterialDelivery.objects.exists():
                MaterialDelivery.objects.create(
                    delivery_number='DEL-2026-0089',
                    supplier='Saudi Plastics Packaging Co.',
                    work_order=wo1,
                    material_code=f"PREFORM-{prod_water.code}",
                    material_name=f"{prod_water.name} PET Preforms",
                    quantity_received=Decimal('50000'),
                    unit_of_measure='PCS',
                    lot_number='LOT-SPP-9921',
                    dock_location='Dock-A (Raw Materials In)',
                    received_at=now - datetime.timedelta(hours=8),
                    received_by=planner_user,
                    notes='Inspected and quality cleared for food-grade contact.'
                )

        # 16. Seed Default Report Subscriptions (Batch 7 - F10)
        from apps.reports.models import ReportSubscription
        manager_user = User.objects.filter(username='manager_demo').first()
        ReportSubscription.objects.update_or_create(
            name='Line 1 Shift Handover Executive Brief',
            defaults={
                'report_type': 'SHIFT_HANDOVER',
                'format': 'BOTH',
                'frequency': 'END_OF_SHIFT',
                'line': line1,
                'recipient_emails': 'ops_lead@factsense.com, supervisor@factsense.local',
                'telegram_chat_id': '@factsense_cairo_ops',
                'is_active': True,
                'created_by': manager_user,
            }
        )
        ReportSubscription.objects.update_or_create(
            name='Line 1 Daily Quality & Weight Giveaway Audit',
            defaults={
                'report_type': 'QUALITY_SPC',
                'format': 'EXCEL',
                'frequency': 'DAILY',
                'line': line1,
                'recipient_emails': 'quality@factsense.local, qa_lead@factsense.com',
                'telegram_chat_id': '',
                'is_active': True,
                'created_by': manager_user,
            }
        )

        self.stdout.write(self.style.SUCCESS("[SUCCESS] Seeded exact reference products, spare parts, alert rules, SPC samples, report subscriptions, and demo users without emojis."))
