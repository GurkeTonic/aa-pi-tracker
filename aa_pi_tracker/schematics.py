"""
Static EVE Online PI production data.
P0 = raw resources (extracted), P1-P4 = processed products.
"""

# ESI type_id → name for P0 raw resources (from ESI extractor product_type_id)
P0_TYPES = {
    2267: "Aqueous Liquids",
    2268: "Base Metals",
    2272: "Carbon Compounds",
    2286: "Complex Organisms",
    2287: "Felsic Magma",
    2288: "Heavy Metals",
    2305: "Ionic Solutions",
    2310: "Micro Organisms",
    2311: "Noble Gas",
    2312: "Noble Metals",
    2313: "Non-CS Crystals",
    2317: "Planktic Colonies",
    2318: "Plant Biomass",
    2319: "Reactive Gas",
    2321: "Suspended Plasma",
}

# ESI schematic_id → schematic name for factory pins
ESI_SCHEMATIC_NAMES = {
    # P1
    1: "Bacteria",
    2: "Biofuels",
    3: "Biomass",
    4: "Chiral Structures",
    5: "Electrolytes",
    6: "Industrial Fibers",
    7: "Oxidizing Compound",
    8: "Oxygen",
    9: "Plasmoids",
    10: "Precious Metals",
    11: "Proteins",
    12: "Reactive Metals",
    13: "Silicon",
    14: "Toxic Metals",
    15: "Water",
    # P2
    16: "Biocells",
    17: "Construction Blocks",
    18: "Consumer Electronics",
    19: "Coolant",
    20: "Enriched Uranium",
    21: "Fertilizer",
    22: "Genetically Enhanced Livestock",
    23: "Livestock",
    24: "Mechanical Parts",
    25: "Microfiber Shielding",
    26: "Miniature Electronics",
    27: "Nanites",
    28: "Oxygen Isotopes",
    29: "Polyaramids",
    30: "Polytextiles",
    31: "Rocket Fuel",
    32: "Silicate Glass",
    33: "Superconductors",
    34: "Supertensile Plastics",
    35: "Synthetic Oil",
    36: "Test Cultures",
    37: "Transmitting Fluids",
    38: "Viral Agent",
    39: "Water-Cooled CPU",
    # P3
    40: "Biotech Research Reports",
    41: "Camera Drones",
    42: "Condensates",
    43: "Cryoprotectant Solution",
    44: "Data Chips",
    45: "Gel-Matrix Biopaste",
    46: "Guidance Systems",
    47: "Hazmat Detection Systems",
    48: "Hermetic Membranes",
    49: "High-Tech Transmitters",
    50: "Industrial Explosives",
    51: "Neocoms",
    52: "Nuclear Reactors",
    53: "Planetary Vehicles",
    54: "Robotics",
    55: "Smartfab Units",
    56: "Sterile Conduits",
    57: "Supercomputers",
    58: "Synthetic Synapses",
    59: "Transcranial Microcontrollers",
    60: "Ukomi Superconductors",
    61: "Vaccines",
    # P4
    62: "Broadcast Node",
    63: "Integrity Response Drones",
    64: "Nano-Factory",
    65: "Organic Mortar Applicators",
    66: "Recursive Computing Module",
    67: "Self-Harmonizing Power Core",
    68: "Wetware Mainframe",
}

# Production schematics keyed by product name.
# output_qty: units per factory cycle
# cycle_time: seconds per cycle
# inputs: {material_name: qty consumed per cycle per factory}
# Tier 1: Basic Industry Facility   (3000 P0 → 20 P1 / 30 min)  = 40 P1/h per factory
# Tier 2: Advanced Industry Facility (40 P1 each → 5 P2 / 60 min) =  5 P2/h per factory
# Tier 3: High-Tech Production Plant (10 P2 each → 3 P3 / 60 min) =  3 P3/h per factory
# Tier 4: Exoplanetary Extraction   (6 P3 each  → 1 P4 / 60 min) =  1 P4/h per factory
SCHEMATICS = {
    # ── P1 ──────────────────────────────────────────────────────────────────
    "Bacteria":            {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Micro Organisms": 3000}},
    "Biofuels":            {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Carbon Compounds": 3000}},
    "Biomass":             {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Planktic Colonies": 3000}},
    "Chiral Structures":   {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Non-CS Crystals": 3000}},
    "Electrolytes":        {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Ionic Solutions": 3000}},
    "Industrial Fibers":   {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Plant Biomass": 3000}},
    "Oxidizing Compound":  {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Reactive Gas": 3000}},
    "Oxygen":              {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Noble Gas": 3000}},
    "Plasmoids":           {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Suspended Plasma": 3000}},
    "Precious Metals":     {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Noble Metals": 3000}},
    "Proteins":            {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Complex Organisms": 3000}},
    "Reactive Metals":     {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Base Metals": 3000}},
    "Silicon":             {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Felsic Magma": 3000}},
    "Toxic Metals":        {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Heavy Metals": 3000}},
    "Water":               {"tier": 1, "output_qty": 20, "cycle_time": 1800, "inputs": {"Aqueous Liquids": 3000}},

    # ── P2 ──────────────────────────────────────────────────────────────────
    "Biocells":                       {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Biofuels": 40, "Proteins": 40}},
    "Construction Blocks":            {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Reactive Metals": 40, "Toxic Metals": 40}},
    "Consumer Electronics":           {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Chiral Structures": 40, "Toxic Metals": 40}},
    "Coolant":                        {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Electrolytes": 40, "Water": 40}},
    "Enriched Uranium":               {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Precious Metals": 40, "Toxic Metals": 40}},
    "Fertilizer":                     {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Bacteria": 40, "Proteins": 40}},
    "Genetically Enhanced Livestock": {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Biomass": 40, "Proteins": 40}},
    "Livestock":                      {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Biomass": 40, "Proteins": 40}},
    "Mechanical Parts":               {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Reactive Metals": 40, "Silicon": 40}},
    "Microfiber Shielding":           {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Industrial Fibers": 40, "Silicon": 40}},
    "Miniature Electronics":          {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Chiral Structures": 40, "Silicon": 40}},
    "Nanites":                        {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Bacteria": 40, "Reactive Metals": 40}},
    "Oxygen Isotopes":                {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Electrolytes": 40, "Oxygen": 40}},
    "Polyaramids":                    {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Industrial Fibers": 40, "Oxidizing Compound": 40}},
    "Polytextiles":                   {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Biomass": 40, "Industrial Fibers": 40}},
    "Rocket Fuel":                    {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Electrolytes": 40, "Plasmoids": 40}},
    "Silicate Glass":                 {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Oxygen": 40, "Silicon": 40}},
    "Superconductors":                {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Plasmoids": 40, "Water": 40}},
    "Supertensile Plastics":          {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Oxygen": 40, "Plasmoids": 40}},
    "Synthetic Oil":                  {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Electrolytes": 40, "Oxygen": 40}},
    "Test Cultures":                  {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Bacteria": 40, "Water": 40}},
    "Transmitting Fluids":            {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Electrolytes": 40, "Oxidizing Compound": 40}},
    "Viral Agent":                    {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Bacteria": 40, "Biomass": 40}},
    "Water-Cooled CPU":               {"tier": 2, "output_qty": 5, "cycle_time": 3600, "inputs": {"Reactive Metals": 40, "Water": 40}},

    # ── P3 ──────────────────────────────────────────────────────────────────
    "Biotech Research Reports":      {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Construction Blocks": 10, "Consumer Electronics": 10, "Livestock": 10}},
    "Camera Drones":                 {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Rocket Fuel": 10, "Silicate Glass": 10}},
    "Condensates":                   {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Coolant": 10, "Oxygen Isotopes": 10}},
    "Cryoprotectant Solution":       {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Fertilizer": 10, "Synthetic Oil": 10, "Water-Cooled CPU": 10}},
    "Data Chips":                    {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Microfiber Shielding": 10, "Superconductors": 10}},
    "Gel-Matrix Biopaste":           {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Biocells": 10, "Oxygen Isotopes": 10, "Superconductors": 10}},
    "Guidance Systems":              {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Miniature Electronics": 10, "Transmitting Fluids": 10}},
    "Hazmat Detection Systems":      {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Polyaramids": 10, "Rocket Fuel": 10, "Transmitting Fluids": 10}},
    "Hermetic Membranes":            {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Genetically Enhanced Livestock": 10, "Polyaramids": 10}},
    "High-Tech Transmitters":        {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Microfiber Shielding": 10, "Transmitting Fluids": 10}},
    "Industrial Explosives":         {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Fertilizer": 10, "Polyaramids": 10}},
    "Neocoms":                       {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Biocells": 10, "Silicate Glass": 10}},
    "Nuclear Reactors":              {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Enriched Uranium": 10, "Microfiber Shielding": 10}},
    "Planetary Vehicles":            {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Mechanical Parts": 10, "Miniature Electronics": 10, "Supertensile Plastics": 10}},
    "Robotics":                      {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Consumer Electronics": 10, "Mechanical Parts": 10}},
    "Smartfab Units":                {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Construction Blocks": 10, "Miniature Electronics": 10}},
    "Sterile Conduits":              {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Nanites": 10, "Silicate Glass": 10}},
    "Supercomputers":                {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Consumer Electronics": 10, "Coolant": 10, "Water-Cooled CPU": 10}},
    "Synthetic Synapses":            {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Nanites": 10, "Supertensile Plastics": 10}},
    "Transcranial Microcontrollers": {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Biocells": 10, "Nanites": 10}},
    "Ukomi Superconductors":         {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Superconductors": 10, "Synthetic Oil": 10}},
    "Vaccines":                      {"tier": 3, "output_qty": 3, "cycle_time": 3600, "inputs": {"Livestock": 10, "Viral Agent": 10}},

    # ── P4 ──────────────────────────────────────────────────────────────────
    "Broadcast Node":              {"tier": 4, "output_qty": 1, "cycle_time": 3600, "inputs": {"Neocoms": 6, "Recursive Computing Module": 6, "Self-Harmonizing Power Core": 6}},
    "Integrity Response Drones":   {"tier": 4, "output_qty": 1, "cycle_time": 3600, "inputs": {"Gel-Matrix Biopaste": 6, "Hazmat Detection Systems": 6, "Planetary Vehicles": 6}},
    "Nano-Factory":                {"tier": 4, "output_qty": 1, "cycle_time": 3600, "inputs": {"Industrial Explosives": 6, "Reactive Gas": 6, "Ukomi Superconductors": 6}},
    "Organic Mortar Applicators":  {"tier": 4, "output_qty": 1, "cycle_time": 3600, "inputs": {"Condensates": 6, "Robotics": 6, "Sterile Conduits": 6}},
    "Recursive Computing Module":  {"tier": 4, "output_qty": 1, "cycle_time": 3600, "inputs": {"Guidance Systems": 6, "Transcranial Microcontrollers": 6, "Ukomi Superconductors": 6}},
    "Self-Harmonizing Power Core": {"tier": 4, "output_qty": 1, "cycle_time": 3600, "inputs": {"Camera Drones": 6, "Hermetic Membranes": 6, "Nuclear Reactors": 6}},
    "Wetware Mainframe":           {"tier": 4, "output_qty": 1, "cycle_time": 3600, "inputs": {"Biotech Research Reports": 6, "Cryoprotectant Solution": 6, "Supercomputers": 6}},
}

# Ordered list for the "Add Objective" dropdown grouped by tier
SCHEMATIC_CHOICES = [
    ("Tier 1", [(n, n) for n, s in sorted(SCHEMATICS.items()) if s["tier"] == 1]),
    ("Tier 2", [(n, n) for n, s in sorted(SCHEMATICS.items()) if s["tier"] == 2]),
    ("Tier 3", [(n, n) for n, s in sorted(SCHEMATICS.items()) if s["tier"] == 3]),
    ("Tier 4", [(n, n) for n, s in sorted(SCHEMATICS.items()) if s["tier"] == 4]),
]


def output_per_hour(schematic_name: str) -> float:
    """Units produced per factory per hour."""
    s = SCHEMATICS[schematic_name]
    return s["output_qty"] * (3600 / s["cycle_time"])


def expand_production(objectives: list) -> tuple:
    """
    Given a list of (schematic_name, target_qty_per_hour), recursively
    expand the full production chain.

    Returns:
        factories: dict {schematic_name → factories_needed (float)}
        extractions: dict {p0_resource_name → units_per_hour_needed (float)}
    """
    from collections import defaultdict

    factories = defaultdict(float)
    extractions = defaultdict(float)

    def _expand(name, qty_per_hour):
        if name not in SCHEMATICS:
            # P0 raw resource
            extractions[name] += qty_per_hour
            return
        s = SCHEMATICS[name]
        cycles_per_hour = 3600 / s["cycle_time"]
        output_rate = s["output_qty"] * cycles_per_hour  # per factory per hour
        needed = qty_per_hour / output_rate
        factories[name] += needed
        for material, qty_per_cycle in s["inputs"].items():
            consumption = needed * qty_per_cycle * cycles_per_hour
            _expand(material, consumption)

    for schematic_name, target in objectives:
        _expand(schematic_name, target)

    return dict(factories), dict(extractions)
