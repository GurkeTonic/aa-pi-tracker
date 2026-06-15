from django.contrib.auth.models import User
from django.db import models


class PiUserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="pi_settings")
    home_system_id = models.BigIntegerField(null=True, blank=True)
    home_system_name = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        default_permissions = ()

    def __str__(self):
        return f"{self.user} — home: {self.home_system_name or '(none)'}"
