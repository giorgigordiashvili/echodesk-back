from django.core.management.base import BaseCommand
from django.utils import timezone
from hr.models import WorkSchedule, LeaveType
from decimal import Decimal


class Command(BaseCommand):
    help = 'Initialize HR system with default work schedules and leave types'

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Initializing HR system...'))
        
        # Create default work schedules
        self.create_work_schedules(options['overwrite'])
        
        # Create default leave types
        self.create_leave_types(options['overwrite'])
        
        self.stdout.write(self.style.SUCCESS('HR system initialization completed!'))

    def create_work_schedules(self, overwrite):
        """Create default work schedules"""
        schedules = [
            {
                'name': 'Standard Full-Time',
                'description': 'Standard Monday to Friday, 9AM to 6PM',
                'schedule_type': 'standard',
                'hours_per_day': Decimal('8.0'),
                'hours_per_week': Decimal('40.0'),
                'monday': True,
                'tuesday': True,
                'wednesday': True,
                'thursday': True,
                'friday': True,
                'saturday': False,
                'sunday': False,
                'start_time': '09:00',
                'end_time': '18:00',
                'break_duration_minutes': 60,
            },
            {
                'name': 'Part-Time (4 hours)',
                'description': 'Part-time schedule, 4 hours per day',
                'schedule_type': 'standard',
                'hours_per_day': Decimal('4.0'),
                'hours_per_week': Decimal('20.0'),
                'monday': True,
                'tuesday': True,
                'wednesday': True,
                'thursday': True,
                'friday': True,
                'saturday': False,
                'sunday': False,
                'start_time': '09:00',
                'end_time': '13:00',
                'break_duration_minutes': 0,
            },
            {
                'name': 'Flexible Schedule',
                'description': 'Flexible working hours with core hours',
                'schedule_type': 'flexible',
                'hours_per_day': Decimal('8.0'),
                'hours_per_week': Decimal('40.0'),
                'monday': True,
                'tuesday': True,
                'wednesday': True,
                'thursday': True,
                'friday': True,
                'saturday': False,
                'sunday': False,
                'start_time': '10:00',
                'end_time': '19:00',
                'break_duration_minutes': 60,
            },
            {
                'name': '6-Day Work Week',
                'description': 'Monday to Saturday work schedule',
                'schedule_type': 'custom',
                'hours_per_day': Decimal('7.0'),
                'hours_per_week': Decimal('42.0'),
                'monday': True,
                'tuesday': True,
                'wednesday': True,
                'thursday': True,
                'friday': True,
                'saturday': True,
                'sunday': False,
                'start_time': '09:00',
                'end_time': '17:00',
                'break_duration_minutes': 60,
            }
        ]
        
        for schedule_data in schedules:
            schedule, created = WorkSchedule.objects.get_or_create(
                name=schedule_data['name'],
                defaults=schedule_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created work schedule: {schedule.name}')
                )
            elif overwrite:
                for key, value in schedule_data.items():
                    setattr(schedule, key, value)
                schedule.save()
                self.stdout.write(
                    self.style.WARNING(f'Updated work schedule: {schedule.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Work schedule already exists: {schedule.name}')
                )

    def create_leave_types(self, overwrite):
        """Create default leave types"""
        leave_types = [
            {
                'name': 'Annual Leave',
                'description': 'Yearly vacation leave for rest and recreation',
                'category': 'annual',
                'max_days_per_year': Decimal('21.0'),
                'allow_carry_over': True,
                'max_carry_over_days': Decimal('5.0'),
                'requires_approval': True,
                'min_notice_days': 7,
                'max_consecutive_days': 14,
                'requires_medical_certificate': False,
                'minimum_service_months': 3,
                'available_to_probationary': False,
                'gender_specific': 'all',
                'is_active': True,
                'is_paid': True,
                'color_code': '#3B82F6',
            },
            {
                'name': 'Sick Leave',
                'description': 'Leave for medical reasons and health issues',
                'category': 'sick',
                'max_days_per_year': Decimal('10.0'),
                'allow_carry_over': False,
                'max_carry_over_days': Decimal('0.0'),
                'requires_approval': True,
                'min_notice_days': 0,
                'max_consecutive_days': None,
                'requires_medical_certificate': True,
                'medical_certificate_threshold_days': 3,
                'minimum_service_months': 0,
                'available_to_probationary': True,
                'gender_specific': 'all',
                'is_active': True,
                'is_paid': True,
                'color_code': '#EF4444',
            },
            {
                'name': 'Maternity Leave',
                'description': 'Leave for new mothers before and after childbirth',
                'category': 'maternity',
                'max_days_per_year': Decimal('126.0'),  # 18 weeks
                'allow_carry_over': False,
                'max_carry_over_days': Decimal('0.0'),
                'requires_approval': True,
                'min_notice_days': 30,
                'max_consecutive_days': None,
                'requires_medical_certificate': True,
                'minimum_service_months': 6,
                'available_to_probationary': False,
                'gender_specific': 'female',
                'is_active': True,
                'is_paid': True,
                'color_code': '#F59E0B',
            },
            {
                'name': 'Paternity Leave',
                'description': 'Leave for new fathers after childbirth',
                'category': 'paternity',
                'max_days_per_year': Decimal('14.0'),  # 2 weeks
                'allow_carry_over': False,
                'max_carry_over_days': Decimal('0.0'),
                'requires_approval': True,
                'min_notice_days': 14,
                'max_consecutive_days': 14,
                'requires_medical_certificate': False,
                'minimum_service_months': 6,
                'available_to_probationary': False,
                'gender_specific': 'male',
                'is_active': True,
                'is_paid': True,
                'color_code': '#10B981',
            },
            {
                'name': 'Personal Leave',
                'description': 'Leave for personal matters and family responsibilities',
                'category': 'personal',
                'max_days_per_year': Decimal('3.0'),
                'allow_carry_over': False,
                'max_carry_over_days': Decimal('0.0'),
                'requires_approval': True,
                'min_notice_days': 3,
                'max_consecutive_days': 3,
                'requires_medical_certificate': False,
                'minimum_service_months': 1,
                'available_to_probationary': False,
                'gender_specific': 'all',
                'is_active': True,
                'is_paid': True,
                'color_code': '#8B5CF6',
            },
            {
                'name': 'Emergency Leave',
                'description': 'Emergency leave for unexpected urgent situations',
                'category': 'emergency',
                'max_days_per_year': Decimal('2.0'),
                'allow_carry_over': False,
                'max_carry_over_days': Decimal('0.0'),
                'requires_approval': False,  # Can be taken immediately
                'min_notice_days': 0,
                'max_consecutive_days': 2,
                'requires_medical_certificate': False,
                'minimum_service_months': 0,
                'available_to_probationary': True,
                'gender_specific': 'all',
                'is_active': True,
                'is_paid': True,
                'color_code': '#DC2626',
            },
            {
                'name': 'Study Leave',
                'description': 'Leave for educational purposes and professional development',
                'category': 'study',
                'max_days_per_year': Decimal('5.0'),
                'allow_carry_over': True,
                'max_carry_over_days': Decimal('2.0'),
                'requires_approval': True,
                'min_notice_days': 14,
                'max_consecutive_days': 5,
                'requires_medical_certificate': False,
                'minimum_service_months': 12,
                'available_to_probationary': False,
                'gender_specific': 'all',
                'is_active': True,
                'is_paid': True,
                'color_code': '#06B6D4',
            },
            {
                'name': 'Unpaid Leave',
                'description': 'Extended leave without pay for personal reasons',
                'category': 'unpaid',
                'max_days_per_year': Decimal('30.0'),
                'allow_carry_over': False,
                'max_carry_over_days': Decimal('0.0'),
                'requires_approval': True,
                'min_notice_days': 30,
                'max_consecutive_days': 30,
                'requires_medical_certificate': False,
                'minimum_service_months': 12,
                'available_to_probationary': False,
                'gender_specific': 'all',
                'is_active': True,
                'is_paid': False,
                'color_code': '#6B7280',
            },
            {
                'name': 'Bereavement Leave',
                'description': 'Leave for family member death and funeral arrangements',
                'category': 'bereavement',
                'max_days_per_year': Decimal('3.0'),
                'allow_carry_over': False,
                'max_carry_over_days': Decimal('0.0'),
                'requires_approval': False,
                'min_notice_days': 0,
                'max_consecutive_days': 3,
                'requires_medical_certificate': False,
                'minimum_service_months': 0,
                'available_to_probationary': True,
                'gender_specific': 'all',
                'is_active': True,
                'is_paid': True,
                'color_code': '#374151',
            }
        ]
        
        for leave_type_data in leave_types:
            leave_type, created = LeaveType.objects.get_or_create(
                name=leave_type_data['name'],
                defaults=leave_type_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created leave type: {leave_type.name}')
                )
            elif overwrite:
                for key, value in leave_type_data.items():
                    setattr(leave_type, key, value)
                leave_type.save()
                self.stdout.write(
                    self.style.WARNING(f'Updated leave type: {leave_type.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Leave type already exists: {leave_type.name}')
                )
