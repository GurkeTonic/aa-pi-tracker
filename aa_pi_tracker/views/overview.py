# Django
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from ..models import PiOwner, PiProject
from ..pi_data import SCHEMATICS, output_per_hour
from .helpers import compute_extractors, get_owners, load_prices, nav_data


@login_required
@permission_required("aa_pi_tracker.view_pi")
def index(request):
    owners = get_owners(request.user, prefetch_planets=True)
    now = timezone.now()
    prices = load_prices()
    prices_synced = bool(prices)

    owners_info = [
        {"owner": o, "planet_count": o.planet_count_ann, "last_sync": o.last_synced}
        for o in owners
    ]
    extractors = compute_extractors(owners, prices, now)

    total_storage_isk = 0
    factory_isk_h = 0
    for owner in owners:
        for planet in owner.planets.all():
            for item in planet.storage_items.all():
                total_storage_isk += item.amount * prices.get(item.type_name, 0)
            for fac in planet.factories.all():
                if fac.schematic_name and fac.schematic_name in SCHEMATICS:
                    factory_isk_h += output_per_hour(fac.schematic_name) * prices.get(
                        fac.schematic_name, 0
                    )

    summary = {
        "expired": sum(1 for e in extractors if e["urgency"] == "expired"),
        "critical": sum(1 for e in extractors if e["urgency"] == "critical"),
        "warning": sum(1 for e in extractors if e["urgency"] == "warning"),
        "active": sum(1 for e in extractors if e["urgency"] == "ok"),
        "total_planets": sum(o["planet_count"] for o in owners_info),
        "total_characters": len(owners_info),
        "total_isk_h": sum(e["isk_per_hour"] for e in extractors),
        "total_storage_isk": total_storage_isk,
    }
    snapshot: dict[str, dict] = {}
    for e in extractors:
        p = e["product"]
        if p not in snapshot:
            snapshot[p] = {"qty_h": 0, "isk_h": 0, "chars": set()}
        snapshot[p]["qty_h"] += e["qty_per_hour"]
        snapshot[p]["isk_h"] += e["isk_per_hour"]
        snapshot[p]["chars"].add(e["character"])
    extraction_snapshot = sorted(
        [
            {
                "product": k,
                "qty_h": v["qty_h"],
                "isk_h": v["isk_h"],
                "char_count": len(v["chars"]),
            }
            for k, v in snapshot.items()
        ],
        key=lambda x: -x["isk_h"],
    )

    last_synced = max((o.last_synced for o in owners if o.last_synced), default=None)

    # Personal projects
    projects_qs = PiProject.objects.filter(
        user=request.user, is_corp_project=False
    ).prefetch_related("objectives", "assigned_planets")
    project_summaries = []
    for proj in projects_qs:
        target_isk_h = sum(
            obj.target_qty_per_hour * prices.get(obj.schematic_name, 0)
            for obj in proj.objectives.all()
        )
        project_summaries.append(
            {
                "pk": proj.pk,
                "name": proj.name,
                "planet_count": len(proj.assigned_planets.all()),
                "target_isk_h": target_isk_h,
                "is_corp": False,
            }
        )

    # Corp projects where user is participant or creator
    user_owner_pks = list(
        PiOwner.objects.filter(user=request.user).values_list("pk", flat=True)
    )
    corp_projects_qs = (
        PiProject.objects.filter(is_corp_project=True)
        .filter(Q(user=request.user) | Q(participants__pk__in=user_owner_pks))
        .distinct()
        .prefetch_related("objectives", "assigned_planets")
    )
    for proj in corp_projects_qs:
        target_isk_h = sum(
            obj.target_qty_per_hour * prices.get(obj.schematic_name, 0)
            for obj in proj.objectives.all()
        )
        project_summaries.append(
            {
                "pk": proj.pk,
                "name": proj.name,
                "planet_count": len(proj.assigned_planets.all()),
                "target_isk_h": target_isk_h,
                "is_corp": True,
            }
        )

    # Extractor timeline: upcoming expiry buckets
    timeline_expired = []
    timeline_critical = []  # < 4h
    timeline_today = []  # 4h – 24h
    timeline_soon = []  # 24h – 72h
    for e in extractors:
        exp = e.get("expiry_time")
        if not exp or e["urgency"] == "expired":
            timeline_expired.append(e)
        else:
            hours = (exp - now).total_seconds() / 3600
            if hours < 4:
                timeline_critical.append(e)
            elif hours < 24:
                timeline_today.append(e)
            elif hours < 72:
                timeline_soon.append(e)

    summary["factory_isk_h"] = factory_isk_h

    ctx = {
        "active_page": "overview",
        "owners_info": owners_info,
        "summary": summary,
        "extraction_snapshot": extraction_snapshot,
        "project_summaries": project_summaries,
        "last_synced": last_synced,
        "prices_synced": prices_synced,
        "timeline_expired": timeline_expired,
        "timeline_critical": timeline_critical,
        "timeline_today": timeline_today,
        "timeline_soon": timeline_soon,
        **nav_data(request, owners),
    }
    return render(request, "aa_pi_tracker/view/overview.html", ctx)
