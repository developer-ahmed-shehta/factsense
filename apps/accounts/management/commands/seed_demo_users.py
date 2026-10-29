"""
Django management command to seed all 10 canonical roles, plant master data,
processes, exact reference screenshot products, and development demo users.
"""

from decimal import Decimal
from datetime import time
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import Role, UserRoleAssignment
from apps.masterdata.models import Factory, Line, Machine, Process, Product, Shift

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
        for scode, sname, sname_ar, st, et, ub, sseq in shifts_data:
            Shift.objects.update_or_create(
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

        # 6. Seed Demo Users
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

        self.stdout.write(self.style.SUCCESS("[SUCCESS] Seeded exact reference products and demo users without emojis."))
