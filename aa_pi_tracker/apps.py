from django.apps import AppConfig

from aa_pi_tracker import __version__


class AaPiTrackerConfig(AppConfig):
    name = "aa_pi_tracker"
    label = "aa_pi_tracker"
    verbose_name = f"PI Tracker v{__version__}"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from celery.schedules import crontab
        from django.conf import settings

        from aa_pi_tracker.app_settings import AA_PI_TRACKER_SYNC_INTERVAL

        if not hasattr(settings, "CELERYBEAT_SCHEDULE"):
            settings.CELERYBEAT_SCHEDULE = {}

        settings.CELERYBEAT_SCHEDULE.setdefault(
            "aa_pi_tracker.tasks.sync_all_pi_data",
            {
                "task": "aa_pi_tracker.tasks.sync_all_pi_data",
                "schedule": crontab(minute=f"*/{AA_PI_TRACKER_SYNC_INTERVAL}"),
                "apply_offset": True,
            },
        )
