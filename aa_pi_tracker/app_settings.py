from django.conf import settings

# ESI both PI endpoints cached 10 minutes; default matches cache window
AA_PI_TRACKER_SYNC_INTERVAL = getattr(settings, "AA_PI_TRACKER_SYNC_INTERVAL", 10)

# Fuzzwork market price sync interval in minutes
AA_PI_TRACKER_PRICE_INTERVAL = getattr(settings, "AA_PI_TRACKER_PRICE_INTERVAL", 30)

# In-app notification: hours before an extractor program expires to warn the owner
AA_PI_TRACKER_EXPIRY_WARN_HOURS = getattr(settings, "AA_PI_TRACKER_EXPIRY_WARN_HOURS", 24)

# Days to keep PiMaintenanceLog rows before the daily cleanup task deletes them
AA_PI_TRACKER_MAINT_LOG_RETENTION_DAYS = getattr(settings, "AA_PI_TRACKER_MAINT_LOG_RETENTION_DAYS", 90)
