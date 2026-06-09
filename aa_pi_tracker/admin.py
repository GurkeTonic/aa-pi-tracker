from django.contrib import admin

from .models import (
    PiExtractorPin,
    PiFactoryPin,
    PiOwner,
    PiPlanet,
    PiProject,
    PiProjectObjective,
    PiProjectPlanet,
)


@admin.register(PiOwner)
class PiOwnerAdmin(admin.ModelAdmin):
    list_display = ("character", "user")
    search_fields = ("character__character_name", "user__username")


class PiExtractorInline(admin.TabularInline):
    model = PiExtractorPin
    extra = 0
    readonly_fields = ("product_name", "cycle_time", "qty_per_cycle", "expiry_time")


class PiFactoryInline(admin.TabularInline):
    model = PiFactoryPin
    extra = 0
    readonly_fields = ("schematic_name",)


@admin.register(PiPlanet)
class PiPlanetAdmin(admin.ModelAdmin):
    list_display = ("planet_name", "owner", "planet_type", "upgrade_level", "last_update")
    list_filter = ("planet_type",)
    search_fields = ("planet_name", "owner__character__character_name")
    inlines = [PiExtractorInline, PiFactoryInline]


class PiObjectiveInline(admin.TabularInline):
    model = PiProjectObjective
    extra = 0


class PiProjectPlanetInline(admin.TabularInline):
    model = PiProjectPlanet
    extra = 0


@admin.register(PiProject)
class PiProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "user")
    search_fields = ("name", "user__username")
    inlines = [PiObjectiveInline, PiProjectPlanetInline]
