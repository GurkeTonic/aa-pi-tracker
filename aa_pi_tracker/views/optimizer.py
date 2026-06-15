# Standard Library
import json

# Django
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from ..models import PiPlanet, PiProjectObjective, PiUserSettings
from ..pi_data import SCHEMATIC_CHOICES, SCHEMATICS, production_plan
from .helpers import get_corp_owners, get_owners, manager_corp_id, nav_data


def _p0_to_p1_map():
    return {
        next(iter(s["inputs"])): name
        for name, s in SCHEMATICS.items()
        if s["tier"] == 1
    }


def _build_project_routing(project):
    """
    Returns (miner_routing, factory_inputs).
    miner_routing: {pp_pk: {"p1": str, "weekly_qty": int, "dests": [...]}}
    factory_inputs: {pp_pk: {"receives": [{"p1", "weekly_qty", "sources": [...]}]}}
    """
    from ..models import PiProjectPlanet

    p0_to_p1 = _p0_to_p1_map()
    objectives = list(project.objectives.all())

    all_p0_rates: dict = {}
    all_miners_per_p0: dict = {}
    all_aifs: dict = {}

    for obj in objectives:
        if obj.schematic_name not in SCHEMATICS:
            continue
        plan = production_plan(obj.schematic_name)
        scale = max(1, obj.target_qty_per_hour)
        for p0, rate in plan["p0_rates"].items():
            all_p0_rates[p0] = all_p0_rates.get(p0, 0) + rate * scale
        for p0, cnt in plan["miners_per_p0"].items():
            all_miners_per_p0[p0] = all_miners_per_p0.get(p0, 0) + cnt * scale
        for sch, cnt in plan["aifs"].items():
            all_aifs[sch] = all_aifs.get(sch, 0) + cnt * scale

    p1_for_factory: set = set()
    for aif_sch in all_aifs:
        if aif_sch not in SCHEMATICS:
            continue
        for inp in SCHEMATICS[aif_sch]["inputs"]:
            if inp in SCHEMATICS and SCHEMATICS[inp]["tier"] == 1:
                p1_for_factory.add(inp)

    all_pps = list(
        project.assigned_planets.select_related("planet__owner__character").all()
    )

    def _char_info(pp):
        if pp.planet and pp.planet.owner:
            return {
                "char_id": pp.planet.owner.character.character_id,
                "char_name": pp.planet.owner.character.character_name,
            }
        return {
            "char_id": pp.planned_char_id or 0,
            "char_name": pp.planned_char_name or "?",
        }

    def _planet_name(pp):
        return (
            pp.planet.planet_name
            if pp.planet
            else (pp.planned_system_name or "New Planet")
        )

    factory_pps = [
        pp
        for pp in all_pps
        if pp.role in (PiProjectPlanet.ROLE_FACTORY, PiProjectPlanet.ROLE_FACTORY_P4)
    ]

    miner_routing = {}
    for pp in all_pps:
        if pp.role != PiProjectPlanet.ROLE_MINER or not pp.assigned_p0:
            continue
        p0 = pp.assigned_p0
        p1 = p0_to_p1.get(p0)
        if not p1:
            continue
        src = _char_info(pp)
        total_miners = max(1, all_miners_per_p0.get(p0, 1))
        p0_rate = all_p0_rates.get(p0, 0) / total_miners
        weekly_qty = int(round(p0_rate / 150.0 * 168))
        dests = []
        for fp in factory_pps:
            fc = _char_info(fp)
            dests.append(
                {
                    "char_id": fc["char_id"],
                    "char_name": fc["char_name"],
                    "planet_name": _planet_name(fp),
                    "pp_pk": fp.pk,
                    "is_cross_char": fc["char_id"] != src["char_id"],
                }
            )
        miner_routing[pp.pk] = {"p1": p1, "weekly_qty": weekly_qty, "dests": dests}

    factory_inputs = {}
    for fp in factory_pps:
        fp_char = _char_info(fp)
        receives = []
        for p1 in sorted(p1_for_factory):
            p0 = next((k for k, v in p0_to_p1.items() if v == p1), None)
            if not p0:
                continue
            total_miners = max(1, all_miners_per_p0.get(p0, 1))
            p0_per_miner = all_p0_rates.get(p0, 0) / total_miners
            weekly_per_miner = int(round(p0_per_miner / 150.0 * 168))
            sources = []
            for mp in all_pps:
                if mp.role != PiProjectPlanet.ROLE_MINER or mp.assigned_p0 != p0:
                    continue
                mc = _char_info(mp)
                sources.append(
                    {
                        "char_id": mc["char_id"],
                        "char_name": mc["char_name"],
                        "planet_name": _planet_name(mp),
                        "pp_pk": mp.pk,
                        "is_cross_char": mc["char_id"] != fp_char["char_id"],
                        "weekly_qty": weekly_per_miner,
                    }
                )
            if sources:
                receives.append(
                    {
                        "p1": p1,
                        "weekly_qty": sum(s["weekly_qty"] for s in sources),
                        "sources": sources,
                    }
                )
        factory_inputs[fp.pk] = {"receives": receives}

    return miner_routing, factory_inputs


@login_required
@permission_required("aa_pi_tracker.view_pi")
def optimizer_page(request):
    from ..optimizer import get_planet_pools

    owners = get_owners(request.user)
    pools = get_planet_pools(request.user)
    has_corp_perm = request.user.has_perm("aa_pi_tracker.manage_corp_pi")
    corp_pools = None
    if has_corp_perm:
        corp_owners = get_corp_owners(request.user)
        if corp_owners:
            corp_pools = get_planet_pools(owners=corp_owners)
    user_settings = PiUserSettings.objects.filter(user=request.user).first()
    ctx = {
        "active_page": "optimizer",
        "schematic_choices": SCHEMATIC_CHOICES,
        "pools": pools,
        "corp_pools": corp_pools,
        "has_corp_perm": has_corp_perm,
        "home_system_id": user_settings.home_system_id if user_settings else None,
        "home_system_name": user_settings.home_system_name if user_settings else "",
        **nav_data(request, owners),
    }
    return render(request, "aa_pi_tracker/view/optimizer.html", ctx)


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def optimizer_analyze_json(request):
    from ..optimizer import analyze_max_isk, analyze_target

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    system_id = data.get("system_id") or None
    try:
        system_id = int(system_id) if system_id else None
        max_jumps = max(0, min(15, int(data.get("max_jumps", 15))))
        tax_rate = max(0.0, min(100.0, float(data.get("tax_rate", 0))))
    except (ValueError, TypeError):
        system_id = None
        max_jumps = 15
        tax_rate = 0.0

    qty_per_hour = max(1, min(50, int(data.get("qty_per_hour", 1))))
    corp_mode = bool(data.get("corp_mode")) and request.user.has_perm(
        "aa_pi_tracker.manage_corp_pi"
    )
    if corp_mode:
        owners = get_corp_owners(request.user)
        if not owners:
            return JsonResponse(
                {"ok": False, "error": "Corp mode: no corp members are sharing PI yet."}
            )
    else:
        owners = None

    mode = data.get("mode")
    if mode == "target":
        target = data.get("target", "").strip()
        if not target:
            return JsonResponse({"error": "No target specified"}, status=400)
        try:
            p4_char_id = int(data["p4_char_id"]) if data.get("p4_char_id") else None
        except (ValueError, TypeError):
            p4_char_id = None
        result = analyze_target(
            request.user,
            target,
            system_id,
            max_jumps,
            tax_rate,
            qty_per_hour,
            owners=owners,
            p4_char_id=p4_char_id,
        )
    elif mode == "max_isk":
        result = analyze_max_isk(
            request.user, system_id, max_jumps, tax_rate, qty_per_hour, owners=owners
        )
    else:
        return JsonResponse({"error": "Invalid mode"}, status=400)

    return JsonResponse({"ok": True, "result": result})


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def optimizer_create_project(request):
    from ..optimizer import create_project as _build_project

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    name = data.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "No project name"}, status=400)
    assignments = data.get("assignments") or [
        {"pk": pk, "role": "", "p0": ""} for pk in data.get("planet_pks", [])
    ]
    if not assignments:
        return JsonResponse({"error": "No planets selected"}, status=400)
    project = _build_project(request.user, name, assignments)
    target_product = data.get("target_product", "").strip()
    target_qty = max(1, min(50, int(data.get("target_qty_per_hour", 1))))
    if target_product and target_product in SCHEMATICS:
        PiProjectObjective.objects.get_or_create(
            project=project,
            schematic_name=target_product,
            defaults={"target_qty_per_hour": target_qty},
        )
    return JsonResponse({"ok": True, "project_pk": project.pk, "name": project.name})


@login_required
@permission_required("aa_pi_tracker.manage_corp_pi")
@require_POST
def optimizer_create_corp_project(request):
    from ..optimizer import create_project as _build_project

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    name = data.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "No project name"}, status=400)
    assignments = data.get("assignments") or [
        {"pk": pk, "role": "", "p0": ""} for pk in data.get("planet_pks", [])
    ]
    if not assignments:
        return JsonResponse({"error": "No planets selected"}, status=400)
    corp_id, corp_name = manager_corp_id(request.user)
    corp_owners = get_corp_owners(request.user)
    allowed_owner_ids = {o.pk for o in corp_owners} if corp_owners else None

    project = _build_project(
        request.user, name, assignments, allowed_owner_ids=allowed_owner_ids
    )
    project.is_corp_project = True
    project.corp_id = corp_id
    project.corp_name = corp_name
    project.save(update_fields=["is_corp_project", "corp_id", "corp_name"])

    char_ids = set()
    planet_pks = [a["pk"] for a in assignments if isinstance(a, dict) and a.get("pk")]
    for planet in PiPlanet.objects.filter(pk__in=planet_pks).select_related(
        "owner__character"
    ):
        char_ids.add(planet.owner.character.character_id)
    for a in assignments:
        if isinstance(a, dict) and a.get("new_slot") and a.get("char_id"):
            char_ids.add(a["char_id"])
    if char_ids and corp_owners:
        project.participants.set(
            [o for o in corp_owners if o.character.character_id in char_ids]
        )

    target_product = data.get("target_product", "").strip()
    target_qty = max(1, min(50, int(data.get("target_qty_per_hour", 1))))
    if target_product and target_product in SCHEMATICS:
        PiProjectObjective.objects.get_or_create(
            project=project,
            schematic_name=target_product,
            defaults={"target_qty_per_hour": target_qty},
        )
    return JsonResponse({"ok": True, "project_pk": project.pk, "name": project.name})


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def save_home_system(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    system_id = data.get("system_id")
    system_name = data.get("system_name", "").strip()[:100]
    try:
        system_id = int(system_id) if system_id else None
    except (ValueError, TypeError):
        system_id = None
    PiUserSettings.objects.update_or_create(
        user=request.user,
        defaults={"home_system_id": system_id, "home_system_name": system_name},
    )
    return JsonResponse({"ok": True})
