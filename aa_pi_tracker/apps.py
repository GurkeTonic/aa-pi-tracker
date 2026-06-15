# Django
from django.apps import AppConfig

# AA PI Tracker
from aa_pi_tracker import __version__


class AaPiTrackerConfig(AppConfig):
    name = "aa_pi_tracker"
    label = "aa_pi_tracker"
    verbose_name = f"PI Tracker v{__version__}"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Third Party
        from celery.schedules import crontab

        # Django
        from django.conf import settings

        # AA PI Tracker
        from aa_pi_tracker.app_settings import AA_PI_TRACKER_SYNC_INTERVAL

        if not hasattr(settings, "CELERYBEAT_SCHEDULE"):
            settings.CELERYBEAT_SCHEDULE = {}

        # PI data sync — respects ESI 10-minute cache; interval configurable
        settings.CELERYBEAT_SCHEDULE.setdefault(
            "aa_pi_tracker.tasks.sync_all_pi_data",
            {
                "task": "aa_pi_tracker.tasks.sync_all_pi_data",
                "schedule": crontab(minute=f"*/{AA_PI_TRACKER_SYNC_INTERVAL}"),
                "apply_offset": True,
            },
        )

        # Market price sync via Fuzzwork — every 30 minutes, configurable
        # AA PI Tracker
        from aa_pi_tracker.app_settings import AA_PI_TRACKER_PRICE_INTERVAL

        settings.CELERYBEAT_SCHEDULE.setdefault(
            "aa_pi_tracker.tasks.sync_market_prices",
            {
                "task": "aa_pi_tracker.tasks.sync_market_prices",
                "schedule": crontab(minute=f"*/{AA_PI_TRACKER_PRICE_INTERVAL}"),
                "apply_offset": True,
            },
        )

        # Extractor-expiry in-app notifications — hourly
        settings.CELERYBEAT_SCHEDULE.setdefault(
            "aa_pi_tracker.tasks.check_extractor_expiry",
            {
                "task": "aa_pi_tracker.tasks.check_extractor_expiry",
                "schedule": crontab(minute=0),
                "apply_offset": True,
            },
        )

        # Maintenance-log retention cleanup — daily at 03:00
        settings.CELERYBEAT_SCHEDULE.setdefault(
            "aa_pi_tracker.tasks.purge_old_maintenance_logs",
            {
                "task": "aa_pi_tracker.tasks.purge_old_maintenance_logs",
                "schedule": crontab(minute=15, hour=3),
                "apply_offset": True,
            },
        )
