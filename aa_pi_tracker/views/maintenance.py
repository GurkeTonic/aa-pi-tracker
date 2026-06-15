# Standard Library
import json

# Django
from django.contrib.auth.decorators import login_required, permission_required
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import PiMaintenanceLog, PiOwner, PiProjectPlanet
from ..pi_data import get_item_tier
from .helpers import fmt_remaining, get_owners, get_project_or_404, nav_data
from .optimizer import _build_project_routing


def _build_maintenance_overview(project, now, user_filter=None):
    chars: dict = {}
    for pp in (
        project.assigned_planets.select_related(
            "planet__owner__user", "planet__owner__character"
        )
        .prefetch_related("planet__extractors", "planet__storage_items")
        .all()
    ):
        if not pp.planet or not pp.planet.owner:
            continue
        if user_filter and pp.planet.owner.user != user_filter:
            continue
        char_id = pp.planet.owner.character.character_id
        char_name = pp.planet.owner.character.character_name
        key = (char_id, char_name)
        if key not in chars:
            chars[key] = {
                "char_id": char_id,
                "char_name": char_name,
                "expired_count": 0,
                "critical_count": 0,
                "pickup_count": 0,
                "delivery_count": 0,
            }
        planet = pp.planet
        if pp.role == PiProjectPlanet.ROLE_MINER:
            for ext in planet.extractors.all():
                _, urgency = fmt_remaining(ext.expiry_time, now)
                if urgency == "expired":
                    chars[key]["expired_count"] += 1
                elif urgency == "critical":
                    chars[key]["critical_count"] += 1
            # Use the prefetched storage_items (truthy check on the cached list);
            # .exists() would ignore the prefetch and fire one query per planet.
            if planet.storage_items.all():
                chars[key]["pickup_count"] += 1
        elif pp.role in (PiProjectPlanet.ROLE_FACTORY, PiProjectPlanet.ROLE_FACTORY_P4):
            chars[key]["delivery_count"] += 1

    result = sorted(
        chars.values(),
        key=lambda x: (-(x["expired_count"] + x["critical_count"]), x["char_name"]),
    )
    for c in result:
        c["has_issues"] = c["expired_count"] + c["critical_count"] > 0
    return result


@login_required
@permission_required("aa_pi_tracker.view_pi")
def maintenance_page(request, pk):
    project = get_project_or_404(request, pk)
    owners = get_owners(request.user)
    now = timezone.now()
    user_filter = (
        None
        if (project.is_corp_project and project.user == request.user)
        else request.user
    )
    chars_data = _build_maintenance_overview(project, now, user_filter=user_filter)
    total_expired = sum(c["expired_count"] for c in chars_data)
    total_critical = sum(c["critical_count"] for c in chars_data)
    # Fetch today's maintenance logs for all chars in this project
    # Django
    from django.utils.timezone import localdate

    today = localdate()
    char_ids = [c["char_id"] for c in chars_data if c["char_id"]]
    logs_today = {
        log.character_id: log
        for log in PiMaintenanceLog.objects.filter(
            project=project, date=today, character_id__in=char_ids
        )
    }
    for c in chars_data:
        log = logs_today.get(c["char_id"])
        c["maint_step"] = log.step if log else 1
        c["maint_done"] = log.done if log else False

    done_count = sum(1 for c in chars_data if c["maint_done"])
    ctx = {
        "active_page": "corp_projects" if project.is_corp_project else "projects",
        "project": project,
        "chars_data": chars_data,
        "total_expired": total_expired,
        "total_critical": total_critical,
        "total_chars": len(chars_data),
        "done_count": done_count,
        **nav_data(request, owners),
    }
    return render(request, "aa_pi_tracker/view/maintenance.html", ctx)


@login_required
@permission_required("aa_pi_tracker.view_pi")
def maintenance_char_page(request, pk, char_pk):
    project = get_project_or_404(request, pk)
    if project.is_corp_project:
        if project.user == request.user:
            # Manager: only participants' chars allowed
            if not project.participants.filter(
                character__character_id=char_pk
            ).exists():
                raise Http404
        else:
            # Participant: only own chars
            if not PiOwner.objects.filter(
                user=request.user, character__character_id=char_pk
            ).exists():
                raise Http404
    owners = get_owners(request.user)
    now = timezone.now()
    miner_routing, factory_inputs = _build_project_routing(project)

    step1_planets = []
    step2_planets = []
    step3_planets = []
    char_name = None

    urgency_order = {"expired": 0, "critical": 1, "warning": 2, "ok": 3}

    for pp in (
        project.assigned_planets.select_related("planet__owner__character")
        .prefetch_related("planet__extractors", "planet__storage_items")
        .all()
    ):
        if not pp.planet or not pp.planet.owner:
            continue
        if pp.planet.owner.character.character_id != char_pk:
            continue
        if not char_name:
            char_name = pp.planet.owner.character.character_name
        planet = pp.planet

        if pp.role == PiProjectPlanet.ROLE_MINER:
            extractors = []
            for ext in planet.extractors.all():
                time_remaining, urgency = fmt_remaining(ext.expiry_time, now)
                progress = 0
                if ext.install_time and ext.expiry_time:
                    total_s = (ext.expiry_time - ext.install_time).total_seconds()
                    elapsed_s = (now - ext.install_time).total_seconds()
                    if total_s > 0:
                        progress = min(100, max(0, int(elapsed_s / total_s * 100)))
                extractors.append(
                    {
                        "resource": ext.product_name or "Unknown",
                        "urgency": urgency,
                        "time_remaining": time_remaining,
                        "progress": progress,
                    }
                )
            worst = (
                min(extractors, key=lambda e: urgency_order.get(e["urgency"], 3))[
                    "urgency"
                ]
                if extractors
                else "ok"
            )
            step1_planets.append(
                {
                    "pk": pp.pk,
                    "planet_name": planet.planet_name,
                    "planet_type": planet.planet_type,
                    "system": planet.solar_system_name or "",
                    "extractors": extractors,
                    "worst_urgency": worst,
                }
            )

            routing = miner_routing.get(pp.pk, {})
            items = []
            for si in planet.storage_items.all():
                items.append(
                    {
                        "name": si.type_name,
                        "tier": get_item_tier(si.type_name),
                        "qty": si.amount,
                        "weekly_plan": (
                            routing.get("weekly_qty", 0)
                            if routing.get("p1") == si.type_name
                            else 0
                        ),
                    }
                )
            p1_name = routing.get("p1")
            if p1_name and not any(i["name"] == p1_name for i in items):
                items.append(
                    {
                        "name": p1_name,
                        "tier": 1,
                        "qty": 0,
                        "weekly_plan": routing.get("weekly_qty", 0),
                    }
                )
            step2_planets.append(
                {
                    "pk": pp.pk,
                    "planet_name": planet.planet_name,
                    "planet_type": planet.planet_type,
                    "system": planet.solar_system_name or "",
                    "items": items,
                    "dests": routing.get("dests", []),
                }
            )

        elif pp.role in (PiProjectPlanet.ROLE_FACTORY, PiProjectPlanet.ROLE_FACTORY_P4):
            fin = factory_inputs.get(pp.pk, {})
            step3_planets.append(
                {
                    "pk": pp.pk,
                    "planet_name": planet.planet_name,
                    "planet_type": planet.planet_type,
                    "role": pp.role,
                    "system": planet.solar_system_name or "",
                    "receives": fin.get("receives", []),
                }
            )

    log = PiMaintenanceLog.for_today(project.pk, char_pk)
    ctx = {
        "active_page": "corp_projects" if project.is_corp_project else "projects",
        "project": project,
        "char_pk": char_pk,
        "char_name": char_name or "Pilot",
        "step1_planets": step1_planets,
        "step2_planets": step2_planets,
        "step3_planets": step3_planets,
        "maint_state": {
            "step": log.step,
            "done": log.done,
            "s1": log.planet_checks.get("s1", []),
            "s2": log.planet_checks.get("s2", []),
            "s3": log.planet_checks.get("s3", []),
        },
        **nav_data(request, owners),
    }
    return render(request, "aa_pi_tracker/view/maintenance_char.html", ctx)


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def maintenance_save_state(request, pk, char_pk):
    project = get_project_or_404(request, pk)
    if project.is_corp_project:
        if project.user == request.user:
            # Manager: only participants' chars allowed (mirror of the GET guard;
            # otherwise a manager could create an orphan log for any character_id).
            if not project.participants.filter(
                character__character_id=char_pk
            ).exists():
                return JsonResponse({"error": "forbidden"}, status=403)
        else:
            # Participant: only own chars
            if not PiOwner.objects.filter(
                user=request.user, character__character_id=char_pk
            ).exists():
                return JsonResponse({"error": "forbidden"}, status=403)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    log = PiMaintenanceLog.for_today(pk, char_pk)
    step = int(data.get("step", log.step))
    done = bool(data.get("done", log.done))
    checks = data.get("checks", log.planet_checks)
    if not isinstance(checks, dict):
        checks = {}

    log.step = max(1, min(4, step))
    log.done = done
    log.planet_checks = {
        "s1": [int(x) for x in checks.get("s1", []) if str(x).isdigit()],
        "s2": [int(x) for x in checks.get("s2", []) if str(x).isdigit()],
        "s3": [int(x) for x in checks.get("s3", []) if str(x).isdigit()],
    }
    log.save()
    return JsonResponse({"ok": True})
