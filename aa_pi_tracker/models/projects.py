from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .core import PiOwner
from .planets import PiPlanet


class PiProject(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pi_projects")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    # Corp Projects
    is_corp_project = models.BooleanField(default=False)
    corp_id = models.BigIntegerField(null=True, blank=True)
    corp_name = models.CharField(max_length=100, blank=True, default="")
    participants = models.ManyToManyField(
        PiOwner, blank=True, related_name="corp_projects"
    )

    class Meta:
        default_permissions = ()
        ordering = ["name"]

    def __str__(self):
        return self.name


class PiProjectObjective(models.Model):
    project = models.ForeignKey(PiProject, on_delete=models.CASCADE, related_name="objectives")
    schematic_name = models.CharField(max_length=100)
    target_qty_per_hour = models.PositiveIntegerField(default=1)

    class Meta:
        default_permissions = ()
        unique_together = ("project", "schematic_name")
        ordering = ["schematic_name"]

    def __str__(self):
        return f"{self.schematic_name} @ {self.target_qty_per_hour}/h"


class PiProjectPlanet(models.Model):
    ROLE_MINER = "miner"
    ROLE_FACTORY = "factory"
    ROLE_FACTORY_P4 = "factory_p4"
    ROLE_CHOICES = [
        (ROLE_MINER, "Miner"),
        (ROLE_FACTORY, "Factory"),
        (ROLE_FACTORY_P4, "P4 Factory"),
    ]

    project = models.ForeignKey(PiProject, on_delete=models.CASCADE, related_name="assigned_planets")
    planet = models.ForeignKey(PiPlanet, null=True, blank=True, on_delete=models.SET_NULL, related_name="project_links")
    role = models.CharField(max_length=20, blank=True, default="", choices=ROLE_CHOICES)
    assigned_p0 = models.CharField(max_length=60, blank=True, default="")
    # Fields for planned (not yet colonized) slots — only set when planet is None
    planned_char_id = models.BigIntegerField(null=True, blank=True)
    planned_char_name = models.CharField(max_length=100, blank=True, default="")
    planned_planet_type = models.CharField(max_length=40, blank=True, default="")
    planned_system_name = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        default_permissions = ()
        ordering = ["role", "planet__planet_name", "planned_char_name"]

    def __str__(self):
        planet_label = self.planet.planet_name if self.planet else (self.planned_system_name or "unplanned")
        return f"{self.project.name} — {self.role} — {planet_label}"


class PiMaintenanceLog(models.Model):
    """Server-side per-day maintenance progress tracking (project × character × date)."""

    project = models.ForeignKey(PiProject, on_delete=models.CASCADE, related_name="maintenance_logs")
    character_id = models.BigIntegerField()
    date = models.DateField()
    # Current step (1-3). 4 means done.
    step = models.PositiveSmallIntegerField(default=1)
    done = models.BooleanField(default=False)
    # JSON: {s1: [pk,...], s2: [...], s3: [...]} — checked planet rows
    planet_checks = models.JSONField(default=dict)

    class Meta:
        default_permissions = ()
        unique_together = ("project", "character_id", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.project.name} — char {self.character_id} — {self.date}"

    @classmethod
    def for_today(cls, project_pk, character_id):
        today = timezone.localdate()
        obj, _ = cls.objects.get_or_create(
            project_id=project_pk,
            character_id=character_id,
            date=today,
            defaults={"step": 1, "done": False, "planet_checks": {}},
        )
        return obj
