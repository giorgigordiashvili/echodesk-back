from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.apps import apps
import logging

logger = logging.getLogger(__name__)


@receiver(post_migrate)
def create_default_work_schedule(sender, **kwargs):
    """
    Create default WorkSchedule after HR migrations run.
    This ensures the default schedule exists with proper values.
    """
    if sender.name != 'hr':
        return
    
    try:
        # Import here to avoid circular imports
        WorkSchedule = apps.get_model('hr', 'WorkSchedule')
        
        # Create default work schedule if it doesn't exist
        default_schedule, created = WorkSchedule.objects.get_or_create(
            name='Standard 9-5',
            defaults={
                'description': 'Standard Monday to Friday, 9 AM to 5 PM',
                'schedule_type': 'standard',
                'hours_per_day': 8.0,
                'hours_per_week': 40.0,
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
                'is_active': True,
            }
        )
        
        if created:
            logger.info("Created default WorkSchedule: Standard 9-5")
        else:
            # Update existing schedule if it has null values
            if default_schedule.hours_per_day is None:
                default_schedule.hours_per_day = 8.0
            if default_schedule.hours_per_week is None:
                default_schedule.hours_per_week = 40.0
            if default_schedule.hours_per_day is None or default_schedule.hours_per_week is None:
                default_schedule.save()
                logger.info("Updated default WorkSchedule with proper hours values")
        
    except Exception as e:
        logger.error(f"Failed to create/update default WorkSchedule: {str(e)}")