from django.contrib.auth.models import User
from django.db import models

from allianceauth.eveonline.models import EveCharacter


class General(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [("view_pi", "Can access PI Tracker")]


class PiOwner(models.Model):
    """ESI character authorized for PI colony access."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pi_owners")
    character = models.OneToOneField(
        EveCharacter, on_delete=models.CASCADE, related_name="pi_owner"
    )

    class Meta:
        ordering = ["character__character_name"]

    def __str__(self):
        return self.character.character_name


class PiPlanet(models.Model):
    """Cached planet data from ESI."""

    PLANET_TYPES = [
        ("temperate", "Temperate"),
        ("barren", "Barren"),
        ("oceanic", "Oceanic"),
        ("ice", "Ice"),
        ("gas", "Gas"),
        ("lava", "Lava"),
        ("storm", "Storm"),
        ("plasma", "Plasma"),
    ]

    owner = models.ForeignKey(PiOwner, on_delete=models.CASCADE, related_name="planets")
    planet_id = models.IntegerField()
    planet_name = models.CharField(max_length=100, default="")
    planet_type = models.CharField(max_length=20, choices=PLANET_TYPES, default="barren")
    upgrade_level = models.IntegerField(default=0)
    last_update = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("owner", "planet_id")
        ordering = ["owner__character__character_name", "planet_name"]

    def __str__(self):
        return f"{self.owner.character.character_name} — {self.planet_name}"


class PiExtractorPin(models.Model):
    """Active extractor pin on a planet."""

    planet = models.ForeignKey(PiPlanet, on_delete=models.CASCADE, related_name="extractors")
    product_type_id = models.IntegerField()
    product_name = models.CharField(max_length=100, default="")
    cycle_time = models.IntegerField(default=1800)  # seconds
    qty_per_cycle = models.IntegerField(default=0)
    expiry_time = models.DateTimeField(null=True, blank=True)
    install_time = models.DateTimeField(null=True, blank=True)
    last_cycle_start = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["planet", "product_name"]

    @property
    def qty_per_hour(self) -> float:
        if self.cycle_time <= 0:
            return 0.0
        return self.qty_per_cycle * (3600 / self.cycle_time)


class PiFactoryPin(models.Model):
    """Factory pin on a planet (Advanced/High-Tech/Prestige facility)."""

    planet = models.ForeignKey(PiPlanet, on_delete=models.CASCADE, related_name="factories")
    schematic_id = models.IntegerField(default=0)
    schematic_name = models.CharField(max_length=100, default="")

    class Meta:
        ordering = ["planet", "schematic_name"]


class PiProject(models.Model):
    """User-defined PI production project."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pi_projects")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PiProjectObjective(models.Model):
    """Target output schematic + qty/h for a project."""

    project = models.ForeignKey(PiProject, on_delete=models.CASCADE, related_name="objectives")
    schematic_name = models.CharField(max_length=100)
    target_qty_per_hour = models.IntegerField(default=1)

    class Meta:
        unique_together = ("project", "schematic_name")
        ordering = ["schematic_name"]

    def __str__(self):
        return f"{self.schematic_name} @ {self.target_qty_per_hour}/h"


class PiProjectPlanet(models.Model):
    """Planet assigned to a project (contributes factories/extractors)."""

    project = models.ForeignKey(
        PiProject, on_delete=models.CASCADE, related_name="assigned_planets"
    )
    planet = models.ForeignKey(PiPlanet, on_delete=models.CASCADE, related_name="project_links")

    class Meta:
        unique_together = ("project", "planet")
        ordering = ["planet__planet_name"]
