import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "sync-all-pairs-every-30-seconds": {
        "task": "market.tasks.sync_all_pairs",
        "schedule": 30.0,  # Runs every 30 seconds (30.0 seconds)
    },
}
