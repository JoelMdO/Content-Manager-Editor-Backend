import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("CMS_DB") #type: ignore
app.config_from_object("django.conf:settings", namespace="CELERY") #type: ignore
app.autodiscover_tasks() #type: ignore
