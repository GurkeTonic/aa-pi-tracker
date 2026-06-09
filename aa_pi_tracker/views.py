from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from esi.decorators import token_required

from allianceauth.services.hooks import get_extension_logger

from .models import PiOwner, PiPlanet, PiProject, PiProjectObjective, PiProjectPlanet
from .schematics import SCHEMATIC_CHOICES, SCHEMATICS, expand_production, output_per_hour
from .tasks import sync_owner_pi_data

logger = get_extension_logger(__name__)


def _fmt_cycle(seconds: int) -> str:
    m = seconds // 60
    return f"{m} min"


def _get_owners(user):
    return PiOwner.objects.filter(user=user).select_related("character")


# ── Character management ──────────────────────────────────────────────────────

@login_required
@permission_required("aa_pi_tracker.view_pi")
@token_required(scopes=["esi-planets.manage_planets.v1"])
def add_character(request, token):
    from allianceauth.eveonline.models import EveCharacter

    try:
        char = EveCharacter.objects.get(character_id=token.character_id)
    except EveCharacter.DoesNotExist:
        messages.error(request, "Charakter nicht in Auth gefunden.")
        return redirect("aa_pi_tracker:index")

    owner, created = PiOwner.objects.get_or_create(character=char, defaults={"user": request.user})
    if created:
        sync_owner_pi_data.delay(owner.pk)
        messages.success(request, f"{char.character_name} hinzugefügt. Sync läuft…")
    else:
        messages.info(request, f"{char.character_name} ist bereits hinterlegt.")
    return redirect("aa_pi_tracker:index")


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def remove_character(request):
    owner_pk = request.POST.get("owner_pk")
    PiOwner.objects.filter(pk=owner_pk, user=request.user).delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def trigger_sync(request):
    for owner in _get_owners(request.user):
        sync_owner_pi_data.delay(owner.pk)
    return JsonResponse({"ok": True})


# ── Main view ─────────────────────────────────────────────────────────────────

@login_required
@permission_required("aa_pi_tracker.view_pi")
def index(request):
    owners = _get_owners(request.user)
    now = timezone.now()

    # Characters tab data
    owners_info = []
    for owner in owners:
        last_sync = (
            owner.planets.filter(last_update__isnull=False)
            .order_by("-last_update")
            .values_list("last_update", flat=True)
            .first()
        )
        owners_info.append({
            "owner": owner,
            "planet_count": owner.planets.count(),
            "last_sync": last_sync,
        })

    # Extractors
    extractors = []
    for owner in owners:
        for planet in owner.planets.prefetch_related("extractors"):
            for ext in planet.extractors.all():
                expired = ext.expiry_time and ext.expiry_time < now
                progress = 0
                if ext.install_time and ext.expiry_time:
                    total = (ext.expiry_time - ext.install_time).total_seconds()
                    elapsed = (now - ext.install_time).total_seconds()
                    if total > 0:
                        progress = min(100, int(elapsed / total * 100))
                extractors.append({
                    "character": owner.character.character_name,
                    "planet_name": planet.planet_name,
                    "planet_type": planet.get_planet_type_display(),
                    "upgrade_level": planet.upgrade_level,
                    "product": ext.product_name,
                    "progress": progress,
                    "expired": expired,
                    "expiry_time": ext.expiry_time,
                    "cycle_time_display": _fmt_cycle(ext.cycle_time),
                    "qty_per_cycle": ext.qty_per_cycle,
                    "qty_per_hour": round(ext.qty_per_hour, 0),
                })

    # Planets
    all_planets = []
    for owner in owners:
        for planet in owner.planets.prefetch_related(
            "extractors", "factories", "project_links__project"
        ):
            assigned_projects = [pp.project.name for pp in planet.project_links.all()]
            content_extractors = defaultdict(int)
            for ext in planet.extractors.all():
                if ext.product_name:
                    content_extractors[ext.product_name] += 1
            content_factories = defaultdict(int)
            for fac in planet.factories.all():
                if fac.schematic_name:
                    content_factories[fac.schematic_name] += 1
            all_planets.append({
                "owner": owner,
                "planet": planet,
                "assigned_projects": assigned_projects,
                "content_extractors": dict(content_extractors),
                "content_factories": dict(content_factories),
            })

    # Projects
    projects = PiProject.objects.filter(user=request.user).prefetch_related(
        "objectives", "assigned_planets__planet__owner__character"
    )

    selected_project_pk = request.GET.get("project")
    selected_project = None
    project_data = None

    if selected_project_pk:
        try:
            selected_project = projects.get(pk=selected_project_pk)
            project_data = _build_project_data(selected_project)
        except PiProject.DoesNotExist:
            pass

    context = {
        "owners_info": owners_info,
        "extractors": sorted(extractors, key=lambda e: e["character"]),
        "all_planets": all_planets,
        "projects": projects,
        "selected_project": selected_project,
        "project_data": project_data,
        "schematic_choices": SCHEMATIC_CHOICES,
        "target_qty_choices": list(range(1, 51)),
    }
    return render(request, "aa_pi_tracker/index.html", context)


def _build_project_data(project: PiProject) -> dict:
    objectives = [(o.schematic_name, o.target_qty_per_hour) for o in project.objectives.all()]
    if not objectives:
        return {"fabrication": [], "extraction": []}

    required_factories, required_extractions = expand_production(objectives)

    assigned_planets = [
        pp.planet
        for pp in project.assigned_planets.select_related(
            "planet__owner__character"
        ).prefetch_related("planet__factories", "planet__extractors")
    ]

    actual_factories: dict[str, float] = defaultdict(float)
    for planet in assigned_planets:
        for fac in planet.factories.all():
            if fac.schematic_name:
                actual_factories[fac.schematic_name] += 1

    actual_extractions: dict[str, float] = defaultdict(float)
    for planet in assigned_planets:
        for ext in planet.extractors.all():
            if ext.product_name:
                actual_extractions[ext.product_name] += ext.qty_per_hour

    fabrication = []
    for schematic_name, factories_needed in sorted(
        required_factories.items(),
        key=lambda x: (-SCHEMATICS[x[0]]["tier"], x[0]),
    ):
        rate = output_per_hour(schematic_name)
        tier = SCHEMATICS[schematic_name]["tier"]
        actual_fac = actual_factories.get(schematic_name, 0)
        production_needed = factories_needed * rate
        actual_production = actual_fac * rate
        missing_factories = actual_fac - factories_needed
        missing_production = actual_production - production_needed
        fabrication.append({
            "schematic": schematic_name,
            "tier": tier,
            "factories_needed": round(factories_needed, 2),
            "actual_factories": actual_fac,
            "missing_factories": round(missing_factories, 2),
            "production_needed": round(production_needed, 2),
            "actual_production": round(actual_production, 2),
            "missing_production": round(missing_production, 2),
        })

    extraction = []
    for resource, needed in sorted(required_extractions.items()):
        actual = actual_extractions.get(resource, 0)
        extraction.append({
            "resource": resource,
            "extraction_needed": round(needed, 0),
            "actual_extraction": round(actual, 0),
            "missing_extraction": round(actual - needed, 0),
        })

    return {
        "fabrication": fabrication,
        "extraction": sorted(extraction, key=lambda x: x["resource"]),
    }


# ── Project AJAX endpoints ────────────────────────────────────────────────────

@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def create_project(request):
    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Name erforderlich"}, status=400)
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
    target = int(request.POST.get("target_qty_per_hour", 1))
    if schematic_name not in SCHEMATICS:
        return JsonResponse({"ok": False, "error": "Unbekanntes Schematic"}, status=400)
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
    target = int(request.POST.get("target_qty_per_hour", obj.target_qty_per_hour))
    obj.target_qty_per_hour = target
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
    return JsonResponse(_build_project_data(project))
