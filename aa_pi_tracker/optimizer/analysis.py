from ..pi_data import MAX_AIFS_PER_FACTORY_PLANET, PLANET_TYPE_SLUG_TO_P0, SCHEMATICS, calculate_poco_tax, production_plan
from .planet_helpers import market_prices
from .routing import SDE_TYPE_ID_TO_SLUG, jump_distances, sde_types_in_range
from .slots import get_char_slots

_P4_TYPES = {"barren", "temperate"}
_AVOID_FACTORY = {"gas"}


def _build_miner_char_queue(char_slots, miner_budget, total_miners, priority_char_id=None):
    """Pre-assign miner slots to chars.

    Primary char fills first (all remaining slots), then other chars in descending
    budget order — each filled completely before moving to the next. This minimises
    the number of chars involved and avoids round-robin spreading among equal-budget chars.
    Returns a list of char_slot dicts (length <= total_miners).
    """
    budget = {cs["char_id"]: miner_budget.get(cs["char_id"], 0) for cs in char_slots}
    queue = []

    if priority_char_id:
        p_cs = next((cs for cs in char_slots if cs["char_id"] == priority_char_id), None)
        if p_cs:
            take = min(budget.get(priority_char_id, 0), total_miners)
            queue.extend([p_cs] * take)
            budget[priority_char_id] = 0

    others = sorted(
        [cs for cs in char_slots if cs["char_id"] != priority_char_id],
        key=lambda c: -budget.get(c["char_id"], 0),
    )
    for cs in others:
        if len(queue) >= total_miners:
            break
        take = min(budget[cs["char_id"]], total_miners - len(queue))
        if take > 0:
            queue.extend([cs] * take)

    return queue


def _pick_char_for_factory(char_slots, new_slot_budget):
    """Return the char with the highest CCU who has a remaining slot (or None).

    Factory planets should go to the highest-skilled char to maximise AIF capacity.
    Falls back to most-slots char if CCU is equal.
    """
    best = None
    for cs in char_slots:
        if new_slot_budget.get(cs["char_id"], 0) <= 0:
            continue
        if best is None:
            best = cs
            continue
        cs_aifs = cs.get("max_aifs", 0)
        best_aifs = best.get("max_aifs", 0)
        if cs_aifs > best_aifs or (cs_aifs == best_aifs and new_slot_budget[cs["char_id"]] > new_slot_budget[best["char_id"]]):
            best = cs
    return best


def _effective_max_aifs(char_slots):
    """Derive the effective max-AIFs-per-factory-planet from available chars.

    Uses the highest CCU across chars whose skill has been synced (CCU > 0).
    Falls back to MAX_AIFS_PER_FACTORY_PLANET (CCU5 default) when no char has
    a synced CCU yet — ensures backward-compat and correct test behaviour.
    """
    synced = [cs["max_aifs"] for cs in char_slots if cs.get("command_center_upgrades", 0) > 0]
    return max(synced) if synced else MAX_AIFS_PER_FACTORY_PLANET


def _new_slot_entry(role, char_slot, sde_ok_types, examples, p0=None, p0_rate=None, no_slots=False):
    """Build an assignment entry for a new (uncolonized) planet slot.

    examples format: {slug: (system_name, jumps, radius_km, planet_name)}
    Best type = fewest jumps, ties broken by smallest radius.
    """
    best_type = (
        min(sde_ok_types, key=lambda t: (examples.get(t, ("?", 999, 999_000, ""))[1],
                                         examples.get(t, ("?", 999, 999_000, ""))[2]))
        if sde_ok_types else None
    )
    ex = examples.get(best_type) if best_type else None
    return {
        "pk": None,
        "role": role,
        "p0": p0,
        "p0_rate_needed": p0_rate,
        "rate_ok": None,
        "char": char_slot["char_name"] if char_slot else None,
        "char_id": char_slot["char_id"] if char_slot else None,
        "new_slot": True,
        "truly_missing": not sde_ok_types,
        "no_slots": no_slots,
        "type": best_type,
        "type_display": best_type.capitalize() if best_type else None,
        "needed_types": sorted(sde_ok_types) if sde_ok_types else [],
        "example_system": ex[0] if ex else None,
        "example_jumps": ex[1] if ex else None,
        "example_radius_km": ex[2] if ex else None,
        "example_planet_name": ex[3] if ex else None,
        "radius_km": None,
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


def analyze_target(user, target_schematic, home_system_id=None, max_jumps=15, tax_rate=0, qty_per_hour=1, *, owners=None, p4_char_id=None):
    if target_schematic not in SCHEMATICS:
        return {"error": f"Unknown schematic: {target_schematic}"}

    tier = SCHEMATICS[target_schematic]["tier"]
    prices = market_prices()
    qty_per_hour = max(1, int(qty_per_hour))

    char_slots = get_char_slots(user, owners=owners)

    # Skill-aware factory capacity: use the best CCU among synced chars.
    # Unsynced chars (CCU=0) are excluded — fall back to CCU5 default so tests
    # and fresh installs behave identically to before.
    eff_max_aifs = _effective_max_aifs(char_slots)

    # qty is applied inside production_plan (single rounding) — never scale the
    # already-ceiled 1× counts afterwards, that over-estimates the plan.
    plan = production_plan(target_schematic, qty_per_hour, max_aifs_per_planet=eff_max_aifs)

    p0_needed = plan["p0_rates"]

    if home_system_id:
        jd = jump_distances(home_system_id, max_jumps)
        sde_avail, sde_examples = sde_types_in_range(jd)
    else:
        jd = {}
        sde_avail = set(SDE_TYPE_ID_TO_SLUG.values())
        sde_examples = {}

    # Slot budget = all non-locked slots per char (free_slots).
    # Existing colonized planets are NOT used as a pool — the optimizer plans
    # neutrally from scratch. Only planets locked in active projects are excluded.
    new_slot_budget = {cs["char_id"]: cs["free_slots"] for cs in char_slots}
    factory_new_budget: dict[int, int] = {}
    factories_to_reserve = plan["factory_planets"]

    # Primary char takes all factory slots they can handle (regardless of tier).
    # Remaining factory slots overflow to highest-CCU chars.
    if p4_char_id and factories_to_reserve > 0:
        can_take = min(factories_to_reserve, new_slot_budget.get(p4_char_id, 0))
        if can_take > 0:
            factory_new_budget[p4_char_id] = can_take
            new_slot_budget[p4_char_id] -= can_take
            factories_to_reserve -= can_take

    for cs in sorted(char_slots, key=lambda c: (-c.get("max_aifs", 0), -new_slot_budget.get(c["char_id"], 0))):
        if factories_to_reserve <= 0:
            break
        if cs["char_id"] == p4_char_id:
            continue
        avail = new_slot_budget[cs["char_id"]]
        take = min(factories_to_reserve, avail)
        if take > 0:
            factory_new_budget[cs["char_id"]] = factory_new_budget.get(cs["char_id"], 0) + take
            new_slot_budget[cs["char_id"]] -= take
            factories_to_reserve -= take

    # Miner queue: primary char fills first, then largest-budget chars completely.
    miner_queue = _build_miner_char_queue(char_slots, new_slot_budget, plan["total_miners"], p4_char_id)
    miner_idx = 0
    miner_assignments = []
    missing_p0 = []

    for p0_name, miner_count in sorted(plan["miners_per_p0"].items()):
        needed_types = {t for t, p0s in PLANET_TYPE_SLUG_TO_P0.items() if p0_name in p0s}
        p0_rate_per_miner = round(p0_needed.get(p0_name, 0) / miner_count, 0)
        sde_ok = needed_types & sde_avail

        for _ in range(miner_count):
            char = miner_queue[miner_idx] if miner_idx < len(miner_queue) else None
            miner_idx += 1
            if sde_ok and char is not None:
                miner_assignments.append(_new_slot_entry(
                    "miner", char, sde_ok, sde_examples,
                    p0=p0_name, p0_rate=p0_rate_per_miner,
                ))
            else:
                missing_p0.append(p0_name)
                miner_assignments.append(_new_slot_entry(
                    "miner", None, sde_ok, sde_examples,
                    p0=p0_name, p0_rate=p0_rate_per_miner,
                    no_slots=bool(sde_ok),
                ))

    factory_slots = []

    def assign_factory(role, allowed_types, blocked_types):
        if allowed_types:
            sde_ok = allowed_types & sde_avail
        elif blocked_types:
            sde_ok = sde_avail - blocked_types
        else:
            sde_ok = set(sde_avail)

        # Primary char uses their pre-reserved factory budget first (all roles).
        if p4_char_id and factory_new_budget.get(p4_char_id, 0) > 0:
            p4_cs = next((cs for cs in char_slots if cs["char_id"] == p4_char_id), None)
            if p4_cs and sde_ok:
                factory_new_budget[p4_char_id] -= 1
                return _new_slot_entry(role, p4_cs, sde_ok, sde_examples)

        char = _pick_char_for_factory(char_slots, factory_new_budget)
        if sde_ok and char is not None:
            factory_new_budget[char["char_id"]] -= 1
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
    new_slots_needed = plan["total_planets"]

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
        "needs_selection": [],
        "assigned_pks": [],
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
    eff_max_aifs = _effective_max_aifs(char_slots)

    # Check if the user's actual free colonized planets include a Barren/Temperate type,
    # or if they have new slots available in a range that has such planets.
    free_planet_types = {p.planet_type for cs in char_slots for p in cs["free_colonized"]}
    has_new_slots = any(cs["new_slots"] > 0 for cs in char_slots)
    has_free_p4_slot = bool(_P4_TYPES & free_planet_types) or (has_new_slots and has_p4_planet)

    prices = market_prices()
    results = []
    for name, s in SCHEMATICS.items():
        # qty applied inside production_plan (single rounding) — plan values are
        # already at qty× scale, so no manual * qty_per_hour below.
        plan = production_plan(name, qty_per_hour, max_aifs_per_planet=eff_max_aifs)
        required_p0 = set(plan["miners_per_p0"].keys())
        missing = required_p0 - available_p0
        if missing:
            continue

        planets_needed = plan["total_planets"]

        if s["tier"] == 1:
            factory_ok = True
        elif s["tier"] == 4:
            factory_ok = has_factory_planet and has_free_p4_slot
        else:
            factory_ok = has_factory_planet
        enough_slots = total_free_slots >= planets_needed
        feasible = factory_ok and enough_slots

        price = prices.get(name, 0)
        isk_per_day_gross = round(plan["output_per_day"] * price, 0)
        tax_cost = calculate_poco_tax(plan, s["tier"], tax_rate)
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
            "miners_needed": plan["total_miners"],
            "factory_planets_needed": plan["factory_planets"],
            "enough_slots": enough_slots,
            "isk_per_hour": round(plan["output_per_hour"] * price, 0),
            "isk_per_hour_net": round(isk_per_day_net / 24, 0),
            "isk_per_hour_true": round(isk_per_day_true / 24, 0),
            "output_per_day": plan["output_per_day"],
            "isk_per_day": isk_per_day_gross,
            "isk_per_day_net": isk_per_day_net,
            "tax_cost_per_day": round(tax_cost, 0),
            "p0_opportunity_cost_per_day": p0_opp_cost_day,
            "isk_per_day_true": isk_per_day_true,
            "output_per_hour": round(plan["output_per_hour"], 4),
            "price": round(price, 0),
        })

    results.sort(key=lambda x: (-x["feasible"], -x["isk_per_hour_true"]))
    return results
