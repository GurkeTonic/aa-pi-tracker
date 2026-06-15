import json

from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from ..models import PiPlanet
from ..pi_data import suggest_factory_setup
from .helpers import compute_planets, get_owners, load_prices, nav_data


@login_required
@permission_required("aa_pi_tracker.view_pi")
def planets_page(request):
    owners = get_owners(request.user, prefetch_planets=True)
    prices = load_prices()
    all_planets = compute_planets(owners, prices)
    ctx = {
        "active_page": "planets",
        "all_planets": all_planets,
        "prices_synced": bool(prices),
        **nav_data(request, owners),
    }
    return render(request, "aa_pi_tracker/view/planets.html", ctx)


@login_required
@permission_required("aa_pi_tracker.view_pi")
def system_search(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})
    from eve_sde.models import SolarSystem
    systems = (
        SolarSystem.objects.filter(name__icontains=q, id__lt=31000000)
        .select_related("constellation__region")
        .values("id", "name", "security_status", "constellation__region__name")[:20]
    )
    return JsonResponse({
        "results": [
            {
                "id": s["id"],
                "name": s["name"],
                "region": s["constellation__region__name"] or "",
                "sec": round(max(s["security_status"] or 0, -1.0), 1),
            }
            for s in systems
        ]
    })


@login_required
@permission_required("aa_pi_tracker.view_pi")
def planet_optimizer_json(request, planet_pk):
    planet = get_object_or_404(PiPlanet, pk=planet_pk, owner__user=request.user)

    extraction_rates: dict[str, float] = {}
    for ext in planet.extractors.all():
        if ext.product_name:
            extraction_rates[ext.product_name] = (
                extraction_rates.get(ext.product_name, 0.0) + ext.avg_per_hour
            )

    actual_factories: dict[str, int] = {}
    for fac in planet.factories.all():
        if fac.schematic_name:
            actual_factories[fac.schematic_name] = actual_factories.get(fac.schematic_name, 0) + 1

    suggestions = suggest_factory_setup(extraction_rates)
    prices = load_prices()

    for chain in suggestions["p1_chains"] + suggestions["p2_chains"]:
        chain["actual_factories"] = actual_factories.get(chain["product"], 0)
        chain["factory_gap"] = chain["actual_factories"] - chain["optimal_factories"]
        chain["isk_per_hour_optimal"] = round(chain["output_per_hour"] * prices.get(chain["product"], 0), 0)

    return JsonResponse({
        "ok": True,
        "planet_name": planet.planet_name,
        "planet_type": planet.get_planet_type_display(),
        "extraction_rates": {k: round(v, 0) for k, v in extraction_rates.items()},
        **suggestions,
    })


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def set_planet_resource(request, planet_pk):
    planet = get_object_or_404(PiPlanet, pk=planet_pk, owner__user=request.user)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    resource = data.get("resource", "").strip()
    planet.user_resource = resource
    planet.save(update_fields=["user_resource"])
    return JsonResponse({"ok": True, "resource": planet.user_resource})
