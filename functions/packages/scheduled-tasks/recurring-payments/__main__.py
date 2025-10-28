"""
DigitalOcean Function: Recurring Payments Processor

This function runs daily at 2 AM UTC to charge saved cards for expiring subscriptions.
It's a serverless wrapper around the Django management command.
"""

import os
import sys
import django
from io import StringIO

# Setup Django environment
sys.path.insert(0, '/opt/virtualenv/lib/python3.11/site-packages')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')
django.setup()

from django.core.management import call_command


def main(event, context):
    """
    Entry point for DigitalOcean scheduled function.

    Args:
        event: Trigger event data (contains cron info for scheduled triggers)
        context: Execution context

    Returns:
        dict: Execution result with status and output
    """
    try:
        # Capture command output
        output = StringIO()

        # Run the Django management command
        call_command('process_recurring_payments', stdout=output)

        output_text = output.getvalue()

        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'message': 'Recurring payments processed successfully',
                'output': output_text,
                'triggered_by': 'digitalocean-scheduler'
            }
        }

    except Exception as e:
        error_msg = f'Error processing recurring payments: {str(e)}'

        return {
            'statusCode': 500,
            'body': {
                'status': 'error',
                'error': error_msg
            }
        }
