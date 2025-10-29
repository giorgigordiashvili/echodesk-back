"""
DigitalOcean Function: Trial Expirations Processor

This function runs daily at 9 AM UTC to process trial subscription expirations.
It charges saved cards automatically when trials end and converts to paid subscriptions.
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
            f'{api_url}/api/cron/process-trial-expirations/',
            headers={'X-Cron-Token': cron_token},
            timeout=300
        )

        response.raise_for_status()
        result = response.json()

        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'message': 'Trial expirations processed successfully',
                'output': result,
                'triggered_by': 'digitalocean-functions'
            }
        }

    except Exception as e:
        error_msg = f'Error processing trial expirations: {str(e)}'

        return {
            'statusCode': 500,
            'body': {
                'status': 'error',
                'error': error_msg
            }
        }
