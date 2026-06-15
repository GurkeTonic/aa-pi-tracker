from django.db import models

from .core import PiOwner
from ..pi_data import extractor_avg_per_hour


class PiPlanet(models.Model):
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
    planet_id = models.BigIntegerField()
    planet_name = models.CharField(max_length=100, blank=True, default="")
    planet_type = models.CharField(max_length=20, choices=PLANET_TYPES, default="barren")
    upgrade_level = models.IntegerField(default=0)
    last_update = models.DateTimeField(null=True, blank=True)
    # Location data populated from SDE
    solar_system_id = models.BigIntegerField(null=True, blank=True)
    solar_system_name = models.CharField(max_length=64, blank=True, default="")
    security_status = models.FloatField(null=True, blank=True)
    constellation_name = models.CharField(max_length=64, blank=True, default="")
    region_name = models.CharField(max_length=64, blank=True, default="")
    # User-set P0 resource for planets without active extractors (optimizer input)
    user_resource = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        default_permissions = ()
        unique_together = ("owner", "planet_id")
        ordering = ["planet_name"]

    def __str__(self):
        return f"{self.owner.character.character_name} — {self.planet_name}"

    @property
    def sec_class(self):
        if self.security_status is None:
            return "secondary"
        if self.security_status >= 0.45:
            return "success"
        if self.security_status >= 0.0:
            return "warning"
        return "danger"

    @property
    def sec_display(self):
        if self.security_status is None:
            return "?"
        return f"{max(self.security_status, -1.0):.1f}"


class PiExtractorPin(models.Model):
    planet = models.ForeignKey(PiPlanet, on_delete=models.CASCADE, related_name="extractors")
    product_type_id = models.IntegerField()
    product_name = models.CharField(max_length=100, blank=True, default="")
    cycle_time = models.IntegerField(default=1800)
    qty_per_cycle = models.IntegerField(default=0)
    head_count = models.IntegerField(default=0)
    expiry_time = models.DateTimeField(null=True, blank=True)
    install_time = models.DateTimeField(null=True, blank=True)
    last_cycle_start = models.DateTimeField(null=True, blank=True)
    # Dedup flag for the in-app expiry warning (reset when a new program is installed)
    notified_expiry = models.BooleanField(default=False)

    class Meta:
        default_permissions = ()
        ordering = ["planet", "product_name"]

    def __str__(self):
        return f"{self.planet} — {self.product_name}"

    @property
    def qty_per_hour(self) -> float:
        if self.cycle_time <= 0:
            return 0.0
        return self.qty_per_cycle * (3600 / self.cycle_time)

    @property
    def avg_per_hour(self) -> float:
        """Full-program average matching EVE's in-game display (decay + noise formula)."""
        result = extractor_avg_per_hour(
            self.install_time, self.expiry_time, self.cycle_time, self.qty_per_cycle
        )
        return result if result is not None else self.qty_per_hour


class PiFactoryPin(models.Model):
    planet = models.ForeignKey(PiPlanet, on_delete=models.CASCADE, related_name="factories")
    schematic_id = models.IntegerField(default=0)
    schematic_name = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        default_permissions = ()
        ordering = ["planet", "schematic_name"]

    def __str__(self):
        return f"{self.planet} — {self.schematic_name}"


class PiStorageItem(models.Model):
    """Aggregated contents of all pins (storage, launchpads) on a planet."""
    planet = models.ForeignKey(PiPlanet, on_delete=models.CASCADE, related_name="storage_items")
    type_id = models.IntegerField()
    type_name = models.CharField(max_length=100)
    amount = models.BigIntegerField(default=0)

    class Meta:
        default_permissions = ()
        unique_together = ("planet", "type_id")
        ordering = ["type_name"]

    def __str__(self):
        return f"{self.planet} — {self.type_name} ×{self.amount:,}"
