import math
from collections import defaultdict

from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..models import PiPlanet, PiProject, PiProjectObjective, PiProjectPlanet
from ..pi_data import SCHEMATIC_CHOICES, SCHEMATICS, expand_production, output_per_hour
from .helpers import compute_planets, get_owners, load_prices, nav_data


def _build_project_data(project: PiProject, prices: dict) -> dict:
    objectives = [(o.schematic_name, o.target_qty_per_hour) for o in project.objectives.all()]

    planet_assignments = []
    colonized_planets = []
    for pp in project.assigned_planets.select_related(
        "planet__owner__character"
    ).prefetch_related("planet__extractors", "planet__factories"):
        planet = pp.planet

        if planet is None:
            planet_assignments.append({
                "pp_pk": pp.pk,
                "planet_pk": None,
                "is_planned": True,
                "role": pp.role or "",
                "display_p0": pp.assigned_p0 or None,
                "planned_p0": pp.assigned_p0 or None,
                "actual_p0": None,
                "planned_char_id": pp.planned_char_id,
                "char_name": pp.planned_char_name or "Unknown",
                "char_id": pp.planned_char_id,
                "planet_name": None,
                "planet_type": pp.planned_planet_type or "",
                "planet_type_display": (pp.planned_planet_type or "").capitalize(),
                "system": pp.planned_system_name or "—",
                "sec": None,
                "sec_class": "",
                "factory_schematics": [],
                "upgrade_level": 0,
            })
            continue

        char = planet.owner.character
        actual_p0 = next(
            (e.product_name for e in planet.extractors.all() if e.product_name), None
        )
        display_p0 = actual_p0 or pp.assigned_p0 or None
        role = pp.role
        if not role:
            if actual_p0:
                role = "miner"
            elif any(f.schematic_name for f in planet.factories.all()):
                role = "factory"
        factory_schematics = sorted(
            {f.schematic_name for f in planet.factories.all() if f.schematic_name}
        )
        colonized_planets.append(planet)
        planet_assignments.append({
            "pp_pk": pp.pk,
            "planet_pk": planet.pk,
            "is_planned": False,
            "planet_name": planet.planet_name,
            "planet_type": planet.planet_type,
            "planet_type_display": planet.get_planet_type_display(),
            "system": planet.solar_system_name,
            "sec": planet.sec_display,
            "sec_class": planet.sec_class,
            "char_name": char.character_name,
            "char_id": char.character_id,
            "role": role,
            "display_p0": display_p0,
            "planned_p0": pp.assigned_p0 or None,
            "actual_p0": actual_p0,
            "factory_schematics": factory_schematics,
            "upgrade_level": planet.upgrade_level,
        })

    if not objectives:
        return {
            "fabrication_flat": [], "fabrication_by_tier": {1: [], 2: [], 3: [], 4: []},
            "fabrication_tiers": [], "extraction": [],
            "total_isk_h_target": 0, "total_isk_h_actual": 0,
            "planet_assignments": planet_assignments,
        }

    required_factories_float, required_extractions = expand_production(objectives)
    assigned_planets = colonized_planets

    actual_factories: dict[str, int] = defaultdict(int)
    for planet in assigned_planets:
        for fac in planet.factories.all():
            if fac.schematic_name:
                actual_factories[fac.schematic_name] += 1

    actual_extractions: dict[str, float] = defaultdict(float)
    for planet in assigned_planets:
        for ext in planet.extractors.all():
            if ext.product_name:
                actual_extractions[ext.product_name] += ext.qty_per_hour

    fabrication_by_tier: dict[int, list] = {1: [], 2: [], 3: [], 4: []}
    for schematic_name, needed_float in sorted(
        required_factories_float.items(),
        key=lambda x: (-SCHEMATICS[x[0]]["tier"], x[0]),
    ):
        needed = math.ceil(needed_float)
        rate = output_per_hour(schematic_name)
        tier = SCHEMATICS[schematic_name]["tier"]
        actual = actual_factories.get(schematic_name, 0)
        gap = actual - needed
        price = prices.get(schematic_name, 0)
        fabrication_by_tier[tier].append({
            "schematic": schematic_name,
            "tier": tier,
            "factories_needed": needed,
            "actual_factories": actual,
            "gap": gap,
            "production_needed": round(needed * rate, 1),
            "actual_production": round(actual * rate, 1),
            "production_gap": round((actual - needed) * rate, 1),
            "isk_h_needed": needed * rate * price,
            "isk_h_actual": actual * rate * price,
        })

    fabrication_flat = []
    for tier in (4, 3, 2, 1):
        fabrication_flat.extend(fabrication_by_tier[tier])

    extraction = []
    for resource, needed in sorted(required_extractions.items()):
        actual = actual_extractions.get(resource, 0)
        price = prices.get(resource, 0)
        extraction.append({
            "resource": resource,
            "extraction_needed": round(needed, 0),
            "actual_extraction": round(actual, 0),
            "gap": round(actual - needed, 0),
            "isk_h_needed": needed * price,
            "isk_h_actual": actual * price,
        })

    total_isk_h_target = sum(qty * prices.get(name, 0) for name, qty in objectives)
    total_isk_h_actual = sum(
        actual_factories.get(name, 0) * output_per_hour(name) * prices.get(name, 0)
        for name, _ in objectives
        if name in SCHEMATICS
    )

    fabrication_tiers = [
        (4, "Advanced Commodities", fabrication_by_tier[4]),
        (3, "Specialized Commodities", fabrication_by_tier[3]),
        (2, "Refined Commodities", fabrication_by_tier[2]),
        (1, "Processed Materials", fabrication_by_tier[1]),
    ]

    real_assignments = [a for a in planet_assignments if not a["is_planned"]]
    miners_total = sum(1 for a in real_assignments if a["role"] == "miner")
    miners_active = sum(1 for a in real_assignments if a["role"] == "miner" and a["actual_p0"])
    factories_total = sum(1 for a in real_assignments if a["role"] in ("factory", "factory_p4"))
    factories_configured = sum(
        1 for a in real_assignments
        if a["role"] in ("factory", "factory_p4") and a["factory_schematics"]
    )
    to_colonize = sum(1 for a in planet_assignments if a["is_planned"])

    return {
        "fabrication_flat": fabrication_flat,
        "fabrication_by_tier": fabrication_by_tier,
        "fabrication_tiers": fabrication_tiers,
        "extraction": sorted(extraction, key=lambda x: x["resource"]),
        "total_isk_h_target": total_isk_h_target,
        "total_isk_h_actual": total_isk_h_actual,
        "planet_assignments": planet_assignments,
        "plan_summary": {
            "miners_total": miners_total,
            "miners_active": miners_active,
            "factories_total": factories_total,
            "factories_configured": factories_configured,
            "to_colonize": to_colonize,
        },
    }


@login_required
@permission_required("aa_pi_tracker.view_pi")
def projects_page(request):
    prices = load_prices()
    projects = PiProject.objects.filter(user=request.user).prefetch_related(
        "objectives", "assigned_planets__planet__owner__character"
    )
    selected_project_pk = request.GET.get("project")
    selected_project = None
    project_data = None
    if selected_project_pk:
        try:
            selected_project = projects.get(pk=selected_project_pk)
            project_data = _build_project_data(selected_project, prices)
        except (PiProject.DoesNotExist, ValueError):
            pass

    owners = get_owners(request.user, prefetch_planets=True)
    all_planets = compute_planets(owners, prices)

    ctx = {
        "active_page": "projects",
        "projects": projects,
        "selected_project": selected_project,
        "project_data": project_data,
        "all_planets": all_planets,
        "schematic_choices": SCHEMATIC_CHOICES,
        "target_qty_choices": list(range(1, 51)),
        "prices_synced": bool(prices),
        **nav_data(request, owners),
    }
    return render(request, "aa_pi_tracker/view/projects.html", ctx)


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def create_project(request):
    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Name is required."}, status=400)
    project = PiProject.objects.create(user=request.user, name=name, description=description)
    return JsonResponse({"ok": True, "pk": project.pk, "name": project.name})


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def delete_project(request, pk):
    project = get_object_or_404(PiProject, pk=pk, user=request.user)
    project.delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def add_objective(request, pk):
    project = get_object_or_404(PiProject, pk=pk, user=request.user)
    schematic_name = request.POST.get("schematic_name", "")
    try:
        target = max(1, int(request.POST.get("target_qty_per_hour", 1)))
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Invalid quantity."}, status=400)
    if schematic_name not in SCHEMATICS:
        return JsonResponse({"ok": False, "error": "Unknown schematic."}, status=400)
    obj, _ = PiProjectObjective.objects.update_or_create(
        project=project,
        schematic_name=schematic_name,
        defaults={"target_qty_per_hour": target},
    )
    return JsonResponse({"ok": True, "id": obj.pk})


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def edit_objective(request, pk):
    obj = get_object_or_404(PiProjectObjective, pk=pk, project__user=request.user)
    obj.target_qty_per_hour = int(request.POST.get("target_qty_per_hour", obj.target_qty_per_hour))
    obj.save(update_fields=["target_qty_per_hour"])
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def delete_objective(request, pk):
    obj = get_object_or_404(PiProjectObjective, pk=pk, project__user=request.user)
    obj.delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def add_project_planet(request, pk):
    project = get_object_or_404(PiProject, pk=pk, user=request.user)
    planet_pk = request.POST.get("planet_pk")
    planet = get_object_or_404(PiPlanet, pk=planet_pk, owner__user=request.user)
    PiProjectPlanet.objects.get_or_create(project=project, planet=planet)
    return JsonResponse({
        "ok": True,
        "planet_pk": planet.pk,
        "planet_name": planet.planet_name,
        "system": planet.solar_system_name,
        "planet_type": planet.get_planet_type_display(),
        "character": planet.owner.character.character_name,
    })


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def remove_project_planet(request, pk):
    pp = get_object_or_404(PiProjectPlanet, pk=pk, project__user=request.user)
    pp.delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_pi_tracker.view_pi")
def project_analysis_json(request, pk):
    project = get_object_or_404(PiProject, pk=pk, user=request.user)
    prices = load_prices()
    return JsonResponse(_build_project_data(project, prices))


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def update_project_planet_role(request, pk):
    pp = get_object_or_404(PiProjectPlanet, pk=pk, project__user=request.user)
    role = request.POST.get("role", "")
    if role not in ("", "miner", "factory", "factory_p4"):
        return JsonResponse({"ok": False, "error": "Invalid role"}, status=400)
    pp.role = role
    pp.save(update_fields=["role"])
    return JsonResponse({"ok": True, "role": role})
