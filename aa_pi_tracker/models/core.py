# Django
from django.contrib.auth.models import User
from django.db import models

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter


class General(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("view_pi", "Can access PI Tracker"),
            ("manage_corp_pi", "Can manage Corp PI Projects"),
        ]


class PiOwner(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pi_owners")
    character = models.OneToOneField(
        EveCharacter, on_delete=models.CASCADE, related_name="pi_owner"
    )
    last_synced = models.DateTimeField(null=True, blank=True)
    # PI Skills — active_skill_level (usable, 0 on Alpha if trained in Omega)
    interplanetary_consolidation = models.IntegerField(null=True, blank=True)
    command_center_upgrades = models.IntegerField(null=True, blank=True)
    planetology = models.IntegerField(null=True, blank=True)
    advanced_planetology = models.IntegerField(null=True, blank=True)
    remote_sensing = models.IntegerField(null=True, blank=True)
    # trained_skill_level (always reflects injected level regardless of account type)
    interplanetary_consolidation_trained = models.IntegerField(null=True, blank=True)
    command_center_upgrades_trained = models.IntegerField(null=True, blank=True)
    planetology_trained = models.IntegerField(null=True, blank=True)
    advanced_planetology_trained = models.IntegerField(null=True, blank=True)
    remote_sensing_trained = models.IntegerField(null=True, blank=True)
    # Corp sharing
    shared_with_corp = models.BooleanField(default=False)

    class Meta:
        default_permissions = ()
        ordering = ["character__character_name"]

    def __str__(self):
        return self.character.character_name

    @property
    def max_planets(self):
        if self.interplanetary_consolidation is None:
            return None
        return self.interplanetary_consolidation + 1
