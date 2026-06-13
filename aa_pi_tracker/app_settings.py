from django.conf import settings

# ESI both PI endpoints cached 10 minutes; default matches cache window
AA_PI_TRACKER_SYNC_INTERVAL = getattr(settings, "AA_PI_TRACKER_SYNC_INTERVAL", 10)

# Fuzzwork market price sync interval in minutes
AA_PI_TRACKER_PRICE_INTERVAL = getattr(settings, "AA_PI_TRACKER_PRICE_INTERVAL", 30)
