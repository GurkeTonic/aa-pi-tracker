from .base import *

PACKAGE = "aa_pi_tracker"

SITE_URL = "https://example.com"
CSRF_TRUSTED_ORIGINS = [SITE_URL]

ROOT_URLCONF = "testauth.urls"
WSGI_APPLICATION = "testauth.wsgi.application"
SECRET_KEY = "aa-pi-tracker-test-secret-key-do-not-use-in-production"

STATIC_ROOT = "/tmp/aa-pi-tracker-test-static/"
STATICFILES_DIRS = []

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

SITE_NAME = "testauth"
DEBUG = False
LOGGING = False

INSTALLED_APPS += [
    "eve_sde",
    PACKAGE,
]

APPS_WITH_PUBLIC_VIEWS = []

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/9",
    }
}

CELERY_TASK_ALWAYS_EAGER = True

ESI_SSO_CLIENT_ID = "dummy"
ESI_SSO_CLIENT_SECRET = "dummy"
ESI_SSO_CALLBACK_URL = "http://localhost:8000"
ESI_USER_CONTACT_EMAIL = "pberbuir@googlemail.com"

REGISTRATION_VERIFY_EMAIL = False
EMAIL_HOST = ""
EMAIL_PORT = 587
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = ""
