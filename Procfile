web: newrelic-admin run-program daphne -b 0.0.0.0 -p 8000 amanati_crm.asgi:application
worker: celery -A amanati_crm worker --loglevel=info --concurrency=2
beat: celery -A amanati_crm beat --loglevel=info
