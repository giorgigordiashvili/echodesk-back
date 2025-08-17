from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from hr.models import EmployeeLeaveBalance, LeaveType, WorkSchedule, EmployeeWorkSchedule
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Initialize leave balances for all employees for a specific year'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            default=timezone.now().year,
            help='Year to initialize leave balances for (default: current year)',
        )
        parser.add_argument(
            '--employees',
            nargs='+',
            type=int,
            help='Specific employee IDs to initialize (default: all active employees)',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing balances',
        )

    def handle(self, *args, **options):
        year = options['year']
        employee_ids = options.get('employees')
        overwrite = options['overwrite']
        
        self.stdout.write(
            self.style.SUCCESS(f'Initializing leave balances for year {year}...')
        )
        
        # Get employees to process
        if employee_ids:
            employees = User.objects.filter(id__in=employee_ids, is_active=True)
            self.stdout.write(f'Processing {len(employee_ids)} specific employees')
        else:
            employees = User.objects.filter(is_active=True)
            self.stdout.write(f'Processing all {employees.count()} active employees')
        
        # Get all active leave types
        leave_types = LeaveType.objects.filter(is_active=True)
        self.stdout.write(f'Found {leave_types.count()} active leave types')
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        for employee in employees:
            self.stdout.write(f'Processing {employee.get_full_name()} ({employee.email})')
            
            # Assign default work schedule if none exists
            if not EmployeeWorkSchedule.objects.filter(employee=employee, is_active=True).exists():
                default_schedule = WorkSchedule.objects.filter(name='Standard Full-Time').first()
                if default_schedule:
                    EmployeeWorkSchedule.objects.create(
                        employee=employee,
                        work_schedule=default_schedule,
                        effective_from=timezone.now().date(),
                        is_active=True
                    )
                    self.stdout.write(
                        self.style.WARNING(f'  Assigned default work schedule to {employee.get_full_name()}')
                    )
            
            for leave_type in leave_types:
                balance, created = EmployeeLeaveBalance.objects.get_or_create(
                    employee=employee,
                    leave_type=leave_type,
                    year=year,
                    defaults={
                        'allocated_days': leave_type.max_days_per_year,
                        'used_days': Decimal('0.0'),
                        'pending_days': Decimal('0.0'),
                        'carried_over_days': Decimal('0.0')
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f'  ✓ Created balance for {leave_type.name}')
                    
                    # Handle carry over from previous year
                    if leave_type.allow_carry_over and year > 2020:  # Reasonable year check
                        try:
                            prev_balance = EmployeeLeaveBalance.objects.get(
                                employee=employee,
                                leave_type=leave_type,
                                year=year - 1
                            )
                            
                            # Calculate carry over
                            available_to_carry = prev_balance.available_days
                            max_carry_over = leave_type.max_carry_over_days
                            carry_over_amount = min(available_to_carry, max_carry_over)
                            
                            if carry_over_amount > 0:
                                balance.carried_over_days = carry_over_amount
                                balance.save()
                                self.stdout.write(
                                    f'    Carried over {carry_over_amount} days from {year-1}'
                                )
                        except EmployeeLeaveBalance.DoesNotExist:
                            pass
                            
                elif overwrite:
                    # Update existing balance
                    balance.allocated_days = leave_type.max_days_per_year
                    balance.save()
                    updated_count += 1
                    self.stdout.write(f'  ↻ Updated balance for {leave_type.name}')
                else:
                    skipped_count += 1
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('Leave balance initialization completed!'))
        self.stdout.write(f'Year: {year}')
        self.stdout.write(f'Employees processed: {employees.count()}')
        self.stdout.write(f'Leave types: {leave_types.count()}')
        self.stdout.write(f'Balances created: {created_count}')
        self.stdout.write(f'Balances updated: {updated_count}')
        self.stdout.write(f'Balances skipped: {skipped_count}')
        
        if not overwrite and skipped_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'Use --overwrite flag to update existing balances ({skipped_count} skipped)'
                )
            )
