import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')

app = Celery('amanati_crm')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
