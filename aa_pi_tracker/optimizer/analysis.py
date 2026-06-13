import math

from ..pi_data import MAX_AIFS_PER_FACTORY_PLANET, PLANET_TYPE_SLUG_TO_P0, SCHEMATICS, calculate_poco_tax, production_plan
from .planet_helpers import extraction_rate, known_p0, market_prices, planet_info, possible_p0
from .routing import SDE_TYPE_ID_TO_SLUG, jump_distances, sde_types_in_range
from .slots import get_char_slots

_P4_TYPES = {"barren", "temperate"}
_AVOID_FACTORY = {"gas"}


def _pick_char_for_new_slot(char_slots, new_slot_budget):
    """Return the char with the most remaining uncolonized slots (or None)."""
    best = None
    for cs in char_slots:
        remaining = new_slot_budget.get(cs["char_id"], 0)
        if remaining > 0:
            if best is None or remaining > new_slot_budget[best["char_id"]]:
                best = cs
    return best


def _new_slot_entry(role, char_slot, sde_ok_types, examples, p0=None, p0_rate=None, no_slots=False):
    """Build an assignment entry for a new (uncolonized) planet slot."""
    best_type = (
        min(sde_ok_types, key=lambda t: examples.get(t, ("?", 999))[1])
        if sde_ok_types else None
    )
    ex_sys, ex_j = examples.get(best_type, (None, None)) if best_type else (None, None)
    return {
        "pk": None,
        "role": role,
        "p0": p0,
        "p0_rate_needed": p0_rate,
        "char": char_slot["char_name"] if char_slot else None,
        "char_id": char_slot["char_id"] if char_slot else None,
        "new_slot": True,
        "truly_missing": not sde_ok_types,
        "no_slots": no_slots,
        "type": best_type,
        "type_display": best_type.capitalize() if best_type else None,
        "needed_types": sorted(sde_ok_types) if sde_ok_types else [],
        "example_system": ex_sys,
        "example_jumps": ex_j,
        "name": None,
        "system": None,
        "sec": None,
        "sec_class": None,
        "jumps": None,
        "known_p0": None,
        "possible_p0": [],
        "rate": None,
        "upgrade_level": None,
    }


def analyze_target(user, target_schematic, home_system_id=None, max_jumps=15, tax_rate=0, qty_per_hour=1, *, owners=None):
    if target_schematic not in SCHEMATICS:
        return {"error": f"Unknown schematic: {target_schematic}"}

    tier = SCHEMATICS[target_schematic]["tier"]
    prices = market_prices()
    qty_per_hour = max(1, int(qty_per_hour))

    plan = production_plan(target_schematic)

    if qty_per_hour > 1:
        plan["miners_per_p0"] = {k: math.ceil(v * qty_per_hour) for k, v in plan["miners_per_p0"].items()}
        plan["total_miners"] = sum(plan["miners_per_p0"].values())
        plan["aifs"] = {k: math.ceil(v * qty_per_hour) for k, v in plan["aifs"].items()}
        plan["htpps"] = {k: math.ceil(v * qty_per_hour) for k, v in plan["htpps"].items()}
        plan["total_aifs"] = sum(plan["aifs"].values())
        plan["factory_planets"] = max(1, math.ceil(plan["total_aifs"] / MAX_AIFS_PER_FACTORY_PLANET)) if (plan["aifs"] or plan["htpps"]) else 0
        plan["total_planets"] = plan["total_miners"] + plan["factory_planets"]
        plan["output_per_hour"] *= qty_per_hour
        plan["output_per_day"] = round(plan["output_per_hour"] * 24, 2)
        plan["p0_rates"] = {k: v * qty_per_hour for k, v in plan["p0_rates"].items()}
        plan["factories"] = {k: v * qty_per_hour for k, v in plan["factories"].items()}

    p0_needed = plan["p0_rates"]

    if home_system_id:
        jd = jump_distances(home_system_id, max_jumps)
        sde_avail, sde_examples = sde_types_in_range(jd)
    else:
        jd = {}
        sde_avail = set(SDE_TYPE_ID_TO_SLUG.values())
        sde_examples = {}

    char_slots = get_char_slots(user, owners=owners)
    new_slot_budget = {cs["char_id"]: cs["new_slots"] for cs in char_slots}

    pool = []
    for cs in char_slots:
        for planet in cs["free_colonized"]:
            if home_system_id and planet.solar_system_id not in jd:
                continue
            pool.append(planet)
    pool.sort(key=lambda p: (0 if known_p0(p) else 1, -(extraction_rate(p) or 0)))

    miner_assignments = []
    missing_p0 = []

    for p0_name, miner_count in sorted(plan["miners_per_p0"].items()):
        needed_types = {t for t, p0s in PLANET_TYPE_SLUG_TO_P0.items() if p0_name in p0s}
        p0_rate_per_miner = round(p0_needed.get(p0_name, 0) / miner_count, 0)

        for _ in range(miner_count):
            candidate = None
            for p in pool:
                if known_p0(p) == p0_name:
                    candidate = p
                    break
            if candidate is None:
                for p in pool:
                    if p.planet_type in needed_types:
                        candidate = p
                        break

            if candidate is not None:
                pool.remove(candidate)
                entry = planet_info(candidate, jd)
                entry.update({
                    "role": "miner",
                    "p0": p0_name,
                    "p0_rate_needed": p0_rate_per_miner,
                    "needed_types": [],
                    "example_system": None,
                    "example_jumps": None,
                })
                miner_assignments.append(entry)
                continue

            sde_ok = needed_types & sde_avail
            char = _pick_char_for_new_slot(char_slots, new_slot_budget)
            if sde_ok and char is not None:
                new_slot_budget[char["char_id"]] -= 1
                miner_assignments.append(_new_slot_entry(
                    "miner", char, sde_ok, sde_examples,
                    p0=p0_name, p0_rate=p0_rate_per_miner,
                ))
                continue

            missing_p0.append(p0_name)
            miner_assignments.append(_new_slot_entry(
                "miner", None, sde_ok, sde_examples,
                p0=p0_name, p0_rate=p0_rate_per_miner,
                no_slots=bool(sde_ok),
            ))

    factory_slots = []

    def assign_factory(role, allowed_types, blocked_types):
        for p in pool:
            if allowed_types and p.planet_type not in allowed_types:
                continue
            if blocked_types and p.planet_type in blocked_types:
                continue
            pool.remove(p)
            entry = planet_info(p, jd)
            entry.update({
                "role": role,
                "p0": None,
                "p0_rate_needed": None,
                "needed_types": [],
                "example_system": None,
                "example_jumps": None,
            })
            return entry

        if allowed_types:
            sde_ok = allowed_types & sde_avail
        elif blocked_types:
            sde_ok = sde_avail - blocked_types
        else:
            sde_ok = set(sde_avail)

        char = _pick_char_for_new_slot(char_slots, new_slot_budget)
        if sde_ok and char is not None:
            new_slot_budget[char["char_id"]] -= 1
            return _new_slot_entry(role, char, sde_ok, sde_examples)

        return _new_slot_entry(role, None, sde_ok, sde_examples, no_slots=bool(sde_ok))

    for i in range(plan["factory_planets"]):
        if tier == 4 and i == plan["factory_planets"] - 1:
            factory_slots.append(assign_factory("factory_p4", _P4_TYPES, None))
        else:
            factory_slots.append(assign_factory("factory", None, _AVOID_FACTORY))

    feasible = (
        (not missing_p0)
        and all(not s.get("truly_missing") and not s.get("no_slots") for s in factory_slots)
        and all(not a.get("truly_missing") and not a.get("no_slots") for a in miner_assignments)
    )
    assigned_pks = (
        [a["pk"] for a in miner_assignments if a.get("pk") is not None]
        + [s["pk"] for s in factory_slots if s.get("pk") is not None]
    )
    new_slots_needed = sum(1 for a in miner_assignments + factory_slots if a.get("new_slot"))

    aifs_display = sorted(
        [{"schematic": n, "tier": SCHEMATICS[n]["tier"], "count": c, "building": "AIF"}
         for n, c in plan["aifs"].items()],
        key=lambda x: (-x["tier"], x["schematic"]),
    )
    htpps_display = sorted(
        [{"schematic": n, "tier": SCHEMATICS[n]["tier"], "count": c, "building": "HTPP"}
         for n, c in plan["htpps"].items()],
        key=lambda x: x["schematic"],
    )
    factories_display = sorted(
        [{"schematic": n, "tier": SCHEMATICS[n]["tier"], "count": round(c, 2)}
         for n, c in plan["factories"].items()
         if n in SCHEMATICS],
        key=lambda x: -x["tier"],
    )

    price = prices.get(target_schematic, 0)
    out_rate = plan["output_per_hour"]
    isk_per_day_gross = round(plan["output_per_day"] * price, 0)
    tax_cost = calculate_poco_tax(plan, tier, tax_rate)
    isk_per_day_net = round(isk_per_day_gross - tax_cost, 0)
    # P0 is processed directly into P1 on the miner planet — never exported or sold.
    # P1 is the price-chain baseline; P0 opportunity cost is always 0.
    p0_opp_cost_day = 0
    isk_per_day_true = isk_per_day_net

    return {
        "target": target_schematic,
        "tier": tier,
        "feasible": feasible,
        "miner_assignments": miner_assignments,
        "factory_slots": factory_slots,
        "missing_p0": missing_p0,
        "factories_per_chain": factories_display,
        "aifs_breakdown": aifs_display,
        "htpps_breakdown": htpps_display,
        "total_planets": plan["total_planets"],
        "total_miners": plan["total_miners"],
        "factory_planets_needed": plan["factory_planets"],
        "output_per_day": plan["output_per_day"],
        "isk_per_day": isk_per_day_gross,
        "isk_per_day_net": isk_per_day_net,
        "tax_cost_per_day": tax_cost,
        "p0_opportunity_cost_per_day": p0_opp_cost_day,
        "isk_per_day_true": isk_per_day_true,
        "tax_rate": tax_rate,
        "isk_per_hour": round(out_rate * price, 0),
        "isk_per_hour_net": round(isk_per_day_net / 24, 0),
        "isk_per_hour_true": round(isk_per_day_true / 24, 0),
        "output_per_hour": round(out_rate, 4),
        "price": round(price, 0),
        "needs_selection": [
            a["pk"] for a in miner_assignments if a.get("pk") and not a.get("known_p0")
        ],
        "assigned_pks": assigned_pks,
        "new_slots_needed": new_slots_needed,
        "sde_avail": sorted(sde_avail),
        "filtered_by_jumps": bool(home_system_id),
    }


def analyze_max_isk(user, home_system_id=None, max_jumps=15, tax_rate=0, qty_per_hour=1, *, owners=None):
    if home_system_id:
        jd = jump_distances(home_system_id, max_jumps)
        sde_avail, _ = sde_types_in_range(jd)
    else:
        sde_avail = set(SDE_TYPE_ID_TO_SLUG.values())

    available_p0 = set()
    for slug in sde_avail:
        available_p0.update(PLANET_TYPE_SLUG_TO_P0.get(slug, []))

    has_p4_planet = bool(_P4_TYPES & sde_avail)
    has_factory_planet = bool(sde_avail - _AVOID_FACTORY)

    char_slots = get_char_slots(user, owners=owners)
    total_free_slots = sum(len(cs["free_colonized"]) + cs["new_slots"] for cs in char_slots)

    prices = market_prices()
    results = []
    for name, s in SCHEMATICS.items():
        plan = production_plan(name)
        required_p0 = set(plan["miners_per_p0"].keys())
        missing = required_p0 - available_p0
        if missing:
            continue

        planets_needed = plan["total_planets"] * qty_per_hour

        if s["tier"] == 1:
            factory_ok = True
        else:
            factory_ok = has_factory_planet and (s["tier"] < 4 or has_p4_planet)
        enough_slots = total_free_slots >= planets_needed
        feasible = factory_ok and enough_slots

        price = prices.get(name, 0)
        isk_per_day_gross = round(plan["output_per_day"] * qty_per_hour * price, 0)
        tax_cost = calculate_poco_tax(plan, s["tier"], tax_rate) * qty_per_hour
        isk_per_day_net = round(isk_per_day_gross - tax_cost, 0)
        p0_opp_cost_day = 0
        isk_per_day_true = isk_per_day_net
        results.append({
            "product": name,
            "tier": s["tier"],
            "feasible": feasible,
            "factory_ok": factory_ok,
            "required_p0": sorted(required_p0),
            "missing_p0": [],
            "planets_needed": planets_needed,
            "miners_needed": plan["total_miners"] * qty_per_hour,
            "factory_planets_needed": plan["factory_planets"] * qty_per_hour,
            "enough_slots": enough_slots,
            "isk_per_hour": round(plan["output_per_hour"] * qty_per_hour * price, 0),
            "isk_per_hour_net": round(isk_per_day_net / 24, 0),
            "isk_per_hour_true": round(isk_per_day_true / 24, 0),
            "output_per_day": plan["output_per_day"] * qty_per_hour,
            "isk_per_day": isk_per_day_gross,
            "isk_per_day_net": isk_per_day_net,
            "tax_cost_per_day": round(tax_cost, 0),
            "p0_opportunity_cost_per_day": p0_opp_cost_day,
            "isk_per_day_true": isk_per_day_true,
            "output_per_hour": round(plan["output_per_hour"] * qty_per_hour, 4),
            "price": round(price, 0),
        })

    results.sort(key=lambda x: (-x["feasible"], -x["isk_per_hour_true"]))
    return results
