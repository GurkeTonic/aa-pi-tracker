from django.contrib import admin

from .models import (
    General,
    PiExtractorPin,
    PiFactoryPin,
    PiMarketPrice,
    PiOwner,
    PiPlanet,
    PiProject,
    PiProjectObjective,
    PiProjectPlanet,
    PiStorageItem,
    PiUserSettings,
)


@admin.register(General)
class GeneralAdmin(admin.ModelAdmin):
    pass


@admin.register(PiOwner)
class PiOwnerAdmin(admin.ModelAdmin):
    list_display = ("character", "user", "last_synced")
    list_select_related = ("character", "user")
    search_fields = ("character__character_name", "user__username")
    readonly_fields = ("last_synced",)


class PiExtractorInline(admin.TabularInline):
    model = PiExtractorPin
    extra = 0
    readonly_fields = ("product_name", "cycle_time", "qty_per_cycle", "expiry_time")


class PiFactoryInline(admin.TabularInline):
    model = PiFactoryPin
    extra = 0
    readonly_fields = ("schematic_name",)


class PiStorageItemInline(admin.TabularInline):
    model = PiStorageItem
    extra = 0
    readonly_fields = ("type_id", "type_name", "amount")


@admin.register(PiPlanet)
class PiPlanetAdmin(admin.ModelAdmin):
    list_display = ("planet_name", "owner", "planet_type", "upgrade_level", "last_update")
    list_filter = ("planet_type",)
    list_select_related = ("owner__character",)
    search_fields = ("planet_name", "owner__character__character_name")
    inlines = [PiExtractorInline, PiFactoryInline, PiStorageItemInline]


@admin.register(PiMarketPrice)
class PiMarketPriceAdmin(admin.ModelAdmin):
    list_display = ("type_name", "tier", "jita_buy", "updated_at")
    list_filter = ("tier",)
    search_fields = ("type_name",)
    readonly_fields = ("updated_at",)


@admin.register(PiUserSettings)
class PiUserSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "home_system_name")
    list_select_related = ("user",)
    search_fields = ("user__username", "home_system_name")


class PiObjectiveInline(admin.TabularInline):
    model = PiProjectObjective
    extra = 0


class PiProjectPlanetInline(admin.TabularInline):
    model = PiProjectPlanet
    extra = 0


@admin.register(PiProject)
class PiProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "user")
    list_select_related = ("user",)
    search_fields = ("name", "user__username")
    inlines = [PiObjectiveInline, PiProjectPlanetInline]
