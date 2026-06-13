import math
from collections import defaultdict

from .planet_resources import PLANET_TYPE_SLUG_TO_P0, POCO_BASE_COSTS, TIER_VOLUMES, P0_TYPES
from .recipes import SCHEMATICS

# Planet capacity limits (CCU5 null-sec standard)
MAX_BIFS_PER_MINER_PLANET = 8    # Basic Industry Facilities per miner planet
MAX_AIFS_PER_FACTORY_PLANET = 24  # Advanced Industry Facilities per factory planet

# P0 resource name → P1 schematic name (derived from tier-1 recipes)
P0_TO_P1: dict[str, str] = {
    next(iter(s["inputs"])): name
    for name, s in SCHEMATICS.items()
    if s["tier"] == 1
}


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
    factories = defaultdict(float)
    extractions = defaultdict(float)

    def _expand(name, qty_per_hour):
        if name not in SCHEMATICS:
            extractions[name] += qty_per_hour
            return
        s = SCHEMATICS[name]
        cycles_per_hour = 3600 / s["cycle_time"]
        output_rate = s["output_qty"] * cycles_per_hour
        needed = qty_per_hour / output_rate
        factories[name] += needed
        for material, qty_per_cycle in s["inputs"].items():
            consumption = needed * qty_per_cycle * cycles_per_hour
            _expand(material, consumption)

    for schematic_name, target in objectives:
        _expand(schematic_name, target)

    return dict(factories), dict(extractions)


def get_item_tier(type_name: str) -> int:
    """Return PI tier (0-4) for a product name, or -1 if unknown."""
    if type_name in P0_TYPES.values():
        return 0
    s = SCHEMATICS.get(type_name)
    return s["tier"] if s else -1


def get_item_volume(type_name: str) -> float:
    """Return standard packaged volume (m³) for a PI item."""
    return TIER_VOLUMES.get(get_item_tier(type_name), 1.0)


def production_plan(target_schematic: str) -> dict:
    """
    Optimal production plan for a target schematic at full 1× output rate.

    Each miner planet runs MAX_BIFS_PER_MINER_PLANET BIFs (CCU5 null-sec standard).
    Each factory planet holds max MAX_AIFS_PER_FACTORY_PLANET AIFs (conservative CCU5 budget).

    Returns:
      miners_per_p0:   {p0_name: count}   — miner planets per P0 resource type
      total_miners:    int
      aifs:            {product_name: count} — Advanced Industry Facilities (tier 2/3, ceiled)
      htpps:           {product_name: count} — High-Tech Production Plants (tier 4, ceiled)
      factories:       dict — full expand_production result incl. P1 BIF counts
      p0_rates:        dict — P0/h demand at 1× rate
      total_aifs:      int  — sum of aifs (AIF-only, excl. HTPP)
      factory_planets: int  — ceil(total_aifs / MAX_AIFS_PER_FACTORY_PLANET)
      total_planets:   int
      output_per_hour: float
      output_per_day:  float
    """
    out_h = output_per_hour(target_schematic)
    factories, p0_rates = expand_production([(target_schematic, out_h)])

    p0_to_p1 = {
        next(iter(s["inputs"])): name
        for name, s in SCHEMATICS.items()
        if s["tier"] == 1
    }

    miners_per_p0 = {}
    for p0_name in p0_rates:
        p1_name = p0_to_p1.get(p0_name)
        bifs = factories.get(p1_name, 0) if p1_name else 0
        miners_per_p0[p0_name] = max(1, math.ceil(bifs / MAX_BIFS_PER_MINER_PLANET))

    # AIFs: Advanced Industry Facilities (tier 2 + tier 3)
    aifs = {
        name: math.ceil(count)
        for name, count in factories.items()
        if SCHEMATICS.get(name, {}).get("tier") in (2, 3)
    }
    # HTpps: High-Tech Production Plants (tier 4 — only on Barren/Temperate)
    htpps = {
        name: math.ceil(count)
        for name, count in factories.items()
        if SCHEMATICS.get(name, {}).get("tier") == 4
    }

    total_aifs = sum(aifs.values())
    # P1: BIFs on miner planet, no factory planet. P2+: at least 1 factory planet.
    factory_planets = max(1, math.ceil(total_aifs / MAX_AIFS_PER_FACTORY_PLANET)) if (aifs or htpps) else 0
    total_miners = sum(miners_per_p0.values())

    return {
        "miners_per_p0": miners_per_p0,
        "total_miners": total_miners,
        "aifs": aifs,
        "htpps": htpps,
        "factories": factories,
        "p0_rates": p0_rates,
        "total_aifs": total_aifs,
        "factory_planets": factory_planets,
        "total_planets": total_miners + factory_planets,
        "output_per_hour": out_h,
        "output_per_day": round(out_h * 24, 2),
    }


def calculate_poco_tax(plan: dict, tier: int, tax_rate: float) -> float:
    """
    Daily POCO tax for a production plan.

    Crossing model (standard: miner planets + consolidated factory planets):
    - P1 export from miner planets + P1 import to factory planets (1.5× combined)
      Only applies when the final product is P2 or higher (tier > 1).
      Includes P1 that flows directly as raw input into P4 schematics.
    - P3 export + import between factory and factory_p4 planets (1.5×)
      Only when tier == 4 and factory_planets > 1.
    - Final product export from the last factory planet (1×).

    tax_rate: percentage value (e.g. 5 for 5%)
    """
    if tax_rate <= 0:
        return 0.0
    rate = tax_rate / 100.0

    # P1 crossing: all P1 leaves miner planets and enters factory planets via POCO.
    # Applies for tier > 1 (when P1 is an intermediate, not the final product itself).
    p1_tax = 0.0
    if tier > 1:
        p1_per_day = sum(
            count * output_per_hour(name) * 24
            for name, count in plan["factories"].items()
            if SCHEMATICS.get(name, {}).get("tier") == 1
        )
        p1_tax = p1_per_day * POCO_BASE_COSTS[1] * 1.5 * rate

    # P3 crossing: when factory_planets > 1 for P4 chains, all P3 flows from
    # factory planet(s) to the factory_p4 planet via POCO.
    p3_tax = 0.0
    if tier == 4 and plan.get("factory_planets", 1) > 1:
        p3_per_day = sum(
            count * output_per_hour(name) * 24
            for name, count in plan["factories"].items()
            if SCHEMATICS.get(name, {}).get("tier") == 3
        )
        p3_tax = p3_per_day * POCO_BASE_COSTS[3] * 1.5 * rate

    # Final product export: the finished goods leave the factory/miner planet.
    final_export_tax = plan["output_per_day"] * POCO_BASE_COSTS[tier] * rate

    return round(p1_tax + p3_tax + final_export_tax, 0)


def suggest_factory_setup(extraction_rates: dict[str, float]) -> dict:
    """
    Given {p0_resource: units_per_hour} from a planet's extractors,
    compute the optimal integer factory counts for P1 (always) and P2
    (only if both required P1 inputs can be produced on the same planet).

    Returns {"p1_chains": [...], "p2_chains": [...]}.
    """
    P0_PER_P1_H = 6000.0
    P1_PER_P2_H = 40.0

    p1_chains: list[dict] = []
    p1_output: dict[str, float] = {}

    for p0, rate in sorted(extraction_rates.items()):
        for p1_name, data in SCHEMATICS.items():
            if data["tier"] != 1:
                continue
            if next(iter(data["inputs"])) != p0:
                continue
            optimal_float = rate / P0_PER_P1_H
            optimal = int(optimal_float)
            if optimal == 0:
                continue
            out_h = optimal * output_per_hour(p1_name)
            p1_output[p1_name] = out_h
            p1_chains.append({
                "product": p1_name,
                "p0_source": p0,
                "optimal_factories_float": round(optimal_float, 2),
                "optimal_factories": optimal,
                "output_per_hour": out_h,
                "p0_consumed_per_hour": optimal * P0_PER_P1_H,
                "p0_available_per_hour": rate,
                "utilization_pct": round(optimal * P0_PER_P1_H / rate * 100, 1),
            })

    p2_chains: list[dict] = []
    for p2_name, p2_data in SCHEMATICS.items():
        if p2_data["tier"] != 2:
            continue
        inputs = p2_data["inputs"]
        if not all(p1 in p1_output for p1 in inputs):
            continue
        limiting = {p1: p1_output[p1] / P1_PER_P2_H for p1 in inputs}
        opt_float = min(limiting.values())
        opt = int(opt_float)
        if opt == 0:
            continue
        bottleneck = min(limiting, key=limiting.get)
        p2_chains.append({
            "product": p2_name,
            "optimal_factories_float": round(opt_float, 2),
            "optimal_factories": opt,
            "output_per_hour": opt * output_per_hour(p2_name),
            "bottleneck_input": bottleneck,
            "inputs": [
                {
                    "p1": p1,
                    "needed_per_hour": opt * P1_PER_P2_H,
                    "available_per_hour": p1_output.get(p1, 0),
                }
                for p1 in inputs
            ],
        })

    p2_chains.sort(key=lambda x: -x["output_per_hour"])
    return {"p1_chains": p1_chains, "p2_chains": p2_chains}
