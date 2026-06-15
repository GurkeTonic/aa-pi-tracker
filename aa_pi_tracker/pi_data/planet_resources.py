# ESI type_id → name for P0 raw resources (from ESI extractor product_type_id)
# Type IDs verified against SDE (groups 1032 Solid, 1033 Liquid-Gas, 1035 Organic)
P0_TYPES = {
    # Solid
    2267: "Base Metals",
    2272: "Heavy Metals",
    2270: "Noble Metals",
    2306: "Non-CS Crystals",
    2307: "Felsic Magma",
    # Liquid-Gas
    2268: "Aqueous Liquids",
    2309: "Ionic Solutions",
    2310: "Noble Gas",
    2311: "Reactive Gas",
    2308: "Suspended Plasma",
    # Organic (PI 2.0 names)
    2073: "Microorganisms",
    2286: "Planktic Colonies",
    2287: "Complex Organisms",
    2288: "Carbon Compounds",
    2305: "Autotrophs",
}

# SDE item_type_id → list of P0 resource names available on that planet type.
# Only the 8 colonizable legacy planet type IDs exist in the SDE
# (django-eveonline-sde): 11/12/13/2014-2017/2063. Shattered (30889) and
# Scorched Barren (73911) are not colonizable and intentionally absent.
# (No "PI 2.0" 560xx type IDs exist in this SDE, so none are mapped here.)
PLANET_TYPE_P0: dict[int, list[str]] = {
    11: [
        "Microorganisms",
        "Aqueous Liquids",
        "Complex Organisms",
        "Carbon Compounds",
        "Autotrophs",
    ],  # Temperate
    12: [
        "Microorganisms",
        "Aqueous Liquids",
        "Heavy Metals",
        "Planktic Colonies",
        "Noble Gas",
    ],  # Ice
    13: [
        "Base Metals",
        "Aqueous Liquids",
        "Ionic Solutions",
        "Noble Gas",
        "Reactive Gas",
    ],  # Gas
    2014: [
        "Microorganisms",
        "Aqueous Liquids",
        "Planktic Colonies",
        "Complex Organisms",
        "Carbon Compounds",
    ],  # Oceanic
    2015: [
        "Base Metals",
        "Heavy Metals",
        "Non-CS Crystals",
        "Felsic Magma",
        "Suspended Plasma",
    ],  # Lava
    2016: [
        "Microorganisms",
        "Base Metals",
        "Noble Metals",
        "Carbon Compounds",
        "Aqueous Liquids",
    ],  # Barren
    2017: [
        "Base Metals",
        "Aqueous Liquids",
        "Suspended Plasma",
        "Ionic Solutions",
        "Noble Gas",
    ],  # Storm
    2063: [
        "Base Metals",
        "Noble Metals",
        "Heavy Metals",
        "Non-CS Crystals",
        "Suspended Plasma",
    ],  # Plasma
}

# Maps PiPlanet.planet_type slug → available P0 resource names
# Uses PI 1.0 SDE type IDs; PI 2.0 variants have identical P0 availability
PLANET_TYPE_SLUG_TO_P0: dict[str, list[str]] = {
    "temperate": PLANET_TYPE_P0[11],
    "ice": PLANET_TYPE_P0[12],
    "gas": PLANET_TYPE_P0[13],
    "oceanic": PLANET_TYPE_P0[2014],
    "lava": PLANET_TYPE_P0[2015],
    "barren": PLANET_TYPE_P0[2016],
    "storm": PLANET_TYPE_P0[2017],
    "plasma": PLANET_TYPE_P0[2063],
}

# PI commodity volumes (m³ per unit) per tier — values from the SDE
# (eve_sde.ItemType.volume), verified 2026-06-13.
TIER_VOLUMES: dict[int, float] = {0: 0.005, 1: 0.19, 2: 0.75, 3: 3.0, 4: 50.0}

# POCO tax base costs per tier (CCP adjusted prices, not market price).
# These are the Dogma attribute ``exportTaxMultiplier`` (1641) on each commodity
# per commodity type, uniform per tier. ``get_poco_base_costs()`` reads them live from
# the SDE (single cached query); the dict below is the verified fallback used
# when the SDE is unavailable.
#   Export tax = qty × base_cost × rate
#   Import tax = qty × base_cost × rate × 0.5
POCO_BASE_COSTS: dict[int, int] = {0: 5, 1: 400, 2: 7_200, 3: 60_000, 4: 1_200_000}

# Dogma attribute id for the POCO export tax base value.
_EXPORT_TAX_MULTIPLIER_ATTR = 1641
# One representative commodity per tier (base value is uniform within a tier).
_TIER_REPRESENTATIVE = {
    0: "Base Metals",
    1: "Bacteria",
    2: "Coolant",
    3: "Robotics",
    4: "Broadcast Node",
}

_poco_base_cache: dict[int, int] | None = None


def get_poco_base_costs() -> dict[int, int]:
    """Per-tier POCO tax base cost, sourced from the SDE Dogma and cached for the
    process. Falls back to ``POCO_BASE_COSTS`` if the SDE is unavailable."""
    global _poco_base_cache
    if _poco_base_cache is not None:
        return _poco_base_cache
    try:
        # Third Party
        from eve_sde.models import ItemType, TypeDogma

        costs: dict[int, int] = {}
        for tier, name in _TIER_REPRESENTATIVE.items():
            it = ItemType.objects.filter(name=name).only("id").first()
            td = (
                TypeDogma.objects.filter(
                    item_type_id=it.id, dogma_attribute_id=_EXPORT_TAX_MULTIPLIER_ATTR
                ).first()
                if it
                else None
            )
            costs[tier] = int(td.value) if td and td.value else POCO_BASE_COSTS[tier]
        _poco_base_cache = costs
    except Exception:
        _poco_base_cache = dict(POCO_BASE_COSTS)
    return _poco_base_cache
