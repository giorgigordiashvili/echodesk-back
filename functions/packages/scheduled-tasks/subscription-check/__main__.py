"""
DigitalOcean Function: Subscription Status Checker

This function runs daily at 3 AM UTC to monitor subscription status,
send email reminders, and suspend overdue accounts.
It calls the Django HTTP endpoint that runs the management command.
"""

import requests
import os


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
        # Get credentials from environment
        cron_token = os.environ.get('CRON_SECRET_TOKEN')
        api_url = os.environ.get('API_URL', 'https://api.echodesk.ge')

        if not cron_token:
            return {
                'statusCode': 500,
                'body': {
                    'status': 'error',
                    'error': 'CRON_SECRET_TOKEN not configured'
                }
            }

        # Call the Django HTTP endpoint
        response = requests.get(
            f'{api_url}/api/cron/subscription-check/',
            headers={'X-Cron-Token': cron_token},
            timeout=300
        )

        response.raise_for_status()
        result = response.json()

        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'message': 'Subscription status check completed successfully',
                'output': result,
                'triggered_by': 'digitalocean-functions'
            }
        }

    except Exception as e:
        error_msg = f'Error checking subscription status: {str(e)}'

        return {
            'statusCode': 500,
            'body': {
                'status': 'error',
                'error': error_msg
            }
        }
