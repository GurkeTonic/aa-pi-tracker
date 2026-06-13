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

# SDE item_type_id → list of P0 resource names available on that planet type
PLANET_TYPE_P0: dict[int, list[str]] = {
    # Legacy planet type IDs
    11:    ["Microorganisms", "Aqueous Liquids", "Complex Organisms", "Carbon Compounds", "Autotrophs"],        # Temperate
    12:    ["Microorganisms", "Aqueous Liquids", "Heavy Metals", "Planktic Colonies", "Noble Gas"],             # Ice
    13:    ["Microorganisms", "Base Metals", "Aqueous Liquids", "Ionic Solutions", "Noble Gas", "Reactive Gas"], # Gas
    2014:  ["Microorganisms", "Aqueous Liquids", "Planktic Colonies", "Complex Organisms", "Carbon Compounds"], # Oceanic
    2015:  ["Base Metals", "Heavy Metals", "Non-CS Crystals", "Felsic Magma", "Suspended Plasma"],             # Lava
    2016:  ["Microorganisms", "Base Metals", "Noble Metals", "Carbon Compounds"],                               # Barren
    2017:  ["Base Metals", "Aqueous Liquids", "Suspended Plasma", "Ionic Solutions", "Noble Gas"],             # Storm
    2063:  ["Base Metals", "Noble Metals", "Heavy Metals", "Non-CS Crystals", "Suspended Plasma"],             # Plasma
    # PI 2.0 planet type IDs
    56018: ["Microorganisms", "Base Metals", "Noble Metals", "Carbon Compounds"],                               # Barren
    56019: ["Microorganisms", "Aqueous Liquids", "Heavy Metals", "Planktic Colonies", "Noble Gas"],             # Ice
    56020: ["Base Metals", "Heavy Metals", "Non-CS Crystals", "Felsic Magma", "Suspended Plasma"],             # Lava
    56021: ["Microorganisms", "Aqueous Liquids", "Planktic Colonies", "Complex Organisms", "Carbon Compounds"], # Oceanic
    56022: ["Base Metals", "Noble Metals", "Heavy Metals", "Non-CS Crystals", "Suspended Plasma"],             # Plasma
    56023: ["Microorganisms", "Aqueous Liquids", "Complex Organisms", "Carbon Compounds", "Autotrophs"],        # Temperate
    56024: ["Base Metals", "Aqueous Liquids", "Suspended Plasma", "Ionic Solutions", "Noble Gas"],             # Storm
}

# Maps PiPlanet.planet_type slug → available P0 resource names
# Uses PI 1.0 SDE type IDs; PI 2.0 variants have identical P0 availability
PLANET_TYPE_SLUG_TO_P0: dict[str, list[str]] = {
    "temperate": PLANET_TYPE_P0[11],
    "ice":       PLANET_TYPE_P0[12],
    "gas":       PLANET_TYPE_P0[13],
    "oceanic":   PLANET_TYPE_P0[2014],
    "lava":      PLANET_TYPE_P0[2015],
    "barren":    PLANET_TYPE_P0[2016],
    "storm":     PLANET_TYPE_P0[2017],
    "plasma":    PLANET_TYPE_P0[2063],
}

# Standard PI item volumes (m³ per unit, well-known EVE packaged values)
TIER_VOLUMES: dict[int, float] = {0: 0.01, 1: 0.38, 2: 1.5, 3: 6.0, 4: 100.0}

# POCO tax base costs per tier (CCP adjusted prices, not market price)
# Source: https://wiki.eveuniversity.org/Planetary_Industry
# Export tax = qty × base_cost × rate
# Import tax = qty × base_cost × rate × 0.5
POCO_BASE_COSTS: dict[int, int] = {0: 5, 1: 400, 2: 7_200, 3: 60_000, 4: 1_200_000}
