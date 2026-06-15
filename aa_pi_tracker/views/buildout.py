import math

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from ..models import PiProjectPlanet
from ..pi_data import MAX_AIFS_PER_FACTORY_PLANET, SCHEMATICS, production_plan
from .helpers import get_owners, get_project_or_404, nav_data
from .optimizer import _p0_to_p1_map


def _slice_aifs(remaining: list, max_count: int) -> tuple:
    """Take up to max_count AIFs from the front of remaining. Returns (taken, rest)."""
    taken = []
    count = 0
    rest = list(remaining)
    while rest and count < max_count:
        e = rest[0]
        take = min(e["count"], max_count - count)
        taken.append({**e, "count": take})
        count += take
        if take == e["count"]:
            rest.pop(0)
        else:
            rest[0] = {**e, "count": e["count"] - take}
    return taken, rest


def _planet_display(pp):
    """Return (planet_name, planet_type, system, is_colonized) for a PiProjectPlanet."""
    if pp.planet:
        return pp.planet.planet_name, pp.planet.planet_type, pp.planet.solar_system_name or "", True
    return pp.planned_system_name or "New Planet", pp.planned_planet_type or "unknown", pp.planned_system_name or "", False


def _build_buildout_data(project, user_filter=None, user_char_ids=None):
    p0_to_p1 = _p0_to_p1_map()
    objectives = list(project.objectives.all())

    # Aggregate AIFs (tier 2/3) and HTpps (tier 4) across all objectives
    combined_aifs: dict = {}
    combined_htpps: dict = {}
    p1_inputs: set = set()

    for obj in objectives:
        if obj.schematic_name not in SCHEMATICS:
            continue
        plan = production_plan(obj.schematic_name)
        scale = max(1, obj.target_qty_per_hour)
        for sch, cnt in plan["aifs"].items():
            combined_aifs[sch] = combined_aifs.get(sch, 0) + math.ceil(cnt * scale)
        for sch, cnt in plan["htpps"].items():
            combined_htpps[sch] = combined_htpps.get(sch, 0) + math.ceil(cnt * scale)

    # Collect all P1 inputs required by AIF/HTPP schematics (needed as POCO imports)
    for sch in list(combined_aifs) + list(combined_htpps):
        for inp in SCHEMATICS.get(sch, {}).get("inputs", {}):
            if inp in SCHEMATICS and SCHEMATICS[inp]["tier"] == 1:
                p1_inputs.add(inp)

    aif_breakdown_full = sorted(
        [{"schematic": n, "tier": SCHEMATICS[n]["tier"], "count": c}
         for n, c in combined_aifs.items() if n in SCHEMATICS],
        key=lambda x: (-x["tier"], x["schematic"]),
    )
    htpp_breakdown_full = sorted(
        [{"schematic": n, "tier": SCHEMATICS[n]["tier"], "count": c}
         for n, c in combined_htpps.items() if n in SCHEMATICS],
        key=lambda x: x["schematic"],
    )
    sorted_p1_inputs = sorted(p1_inputs)

    # Load all assigned planets in one query
    all_pps = list(project.assigned_planets.select_related(
        "planet__owner__user", "planet__owner__character"
    ).order_by("planned_char_name", "planet__owner__character__character_name", "role"))

    # Pre-compute AIF allocation per factory planet.
    # Process order: "factory" planets first (takes up to MAX_AIFS each),
    # then "factory_p4" (gets all remaining AIFs + HTpps).
    factory_pps = sorted(
        [pp for pp in all_pps if pp.role in (PiProjectPlanet.ROLE_FACTORY, PiProjectPlanet.ROLE_FACTORY_P4)],
        key=lambda pp: (0 if pp.role == PiProjectPlanet.ROLE_FACTORY else 1, pp.pk or 0),
    )
    remaining_aifs = [e.copy() for e in aif_breakdown_full]
    aif_alloc: dict = {}  # pp.pk → (my_aifs, my_htpps)

    for i, pp in enumerate(factory_pps):
        is_last = (i == len(factory_pps) - 1)
        is_p4_role = (pp.role == PiProjectPlanet.ROLE_FACTORY_P4)

        if is_last or is_p4_role:
            aif_alloc[pp.pk] = (remaining_aifs[:], htpp_breakdown_full if is_p4_role else [])
            remaining_aifs = []
        else:
            my_aifs, remaining_aifs = _slice_aifs(remaining_aifs, MAX_AIFS_PER_FACTORY_PLANET)
            aif_alloc[pp.pk] = (my_aifs, [])

    # Build display structure grouped by character
    chars: dict = {}
    for pp in all_pps:
        if pp.planet and pp.planet.owner:
            if user_filter and pp.planet.owner.user != user_filter:
                continue
            char_id = pp.planet.owner.character.character_id
            char_name = pp.planet.owner.character.character_name
        else:
            if user_filter:
                if not pp.planned_char_id:
                    continue
                if user_char_ids is not None and pp.planned_char_id not in user_char_ids:
                    continue
            char_id = pp.planned_char_id or 0
            char_name = pp.planned_char_name or "Unassigned"

        key = (char_id, char_name)
        if key not in chars:
            chars[key] = {"char_id": char_id, "char_name": char_name, "planets": []}

        if pp.role == PiProjectPlanet.ROLE_MINER:
            entry = _buildout_miner_entry(pp, p0_to_p1)
        else:
            my_aifs, my_htpps = aif_alloc.get(pp.pk, ([], []))
            entry = _buildout_factory_entry(pp, my_aifs, my_htpps, sorted_p1_inputs)

        chars[key]["planets"].append(entry)

    return [v for _, v in sorted(chars.items(), key=lambda kv: kv[0][1])]


def _buildout_miner_entry(pp, p0_to_p1):
    planet_name, planet_type, system, is_colonized = _planet_display(pp)
    p0 = pp.assigned_p0 or ""
    return {
        "pk": pp.pk,
        "role": pp.role,
        "planet_name": planet_name,
        "planet_type": planet_type,
        "system": system,
        "is_colonized": is_colonized,
        "extracts": p0,
        "produces": p0_to_p1.get(p0, ""),
        "layout": {"ccu": 4, "extractors": 1, "bifs": 8, "aifs": None, "htpps": None, "launchpads": 1},
        "aif_breakdown": [],
        "htpp_breakdown": [],
        "p1_inputs": [],
    }


def _buildout_factory_entry(pp, my_aifs, my_htpps, p1_inputs):
    planet_name, planet_type, system, is_colonized = _planet_display(pp)
    aif_count = sum(e["count"] for e in my_aifs)
    htpp_count = sum(e["count"] for e in my_htpps)
    return {
        "pk": pp.pk,
        "role": pp.role,
        "planet_name": planet_name,
        "planet_type": planet_type,
        "system": system,
        "is_colonized": is_colonized,
        "extracts": "",
        "produces": "",
        "layout": {
            "ccu": 4,
            "extractors": None,
            "bifs": None,
            "aifs": aif_count or None,
            "htpps": htpp_count or None,
            "launchpads": 1,
        },
        "aif_breakdown": my_aifs,
        "htpp_breakdown": my_htpps,
        "p1_inputs": p1_inputs,
    }


@login_required
@permission_required("aa_pi_tracker.view_pi")
def buildout_page(request, pk):
    project = get_project_or_404(request, pk)
    owners = get_owners(request.user)
    user_filter = (
        None
        if (project.is_corp_project and project.user == request.user)
        else request.user
    )
    user_char_ids = {o.character.character_id for o in owners} if user_filter else None
    chars_data = _build_buildout_data(project, user_filter=user_filter, user_char_ids=user_char_ids)
    ctx = {
        "active_page": "corp_projects" if project.is_corp_project else "projects",
        "project": project,
        "chars_data": chars_data,
        "total_planets": project.assigned_planets.count(),
        **nav_data(request, owners),
    }
    return render(request, "aa_pi_tracker/view/buildout.html", ctx)
