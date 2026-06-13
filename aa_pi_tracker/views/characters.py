from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from esi.decorators import token_required

from ..models import PiOwner
from ..tasks import sync_market_prices, sync_owner_pi_data
from .helpers import get_owners, nav_data


@login_required
@permission_required("aa_pi_tracker.view_pi")
@token_required(scopes=["esi-planets.manage_planets.v1", "esi-skills.read_skills.v1"])
def add_character(request, token):
    from allianceauth.eveonline.models import EveCharacter

    try:
        char = EveCharacter.objects.get(character_id=token.character_id)
    except EveCharacter.DoesNotExist:
        messages.error(request, "Character not found in Auth.")
        return redirect("aa_pi_tracker:index")

    owner, created = PiOwner.objects.get_or_create(
        character=char, defaults={"user": request.user}
    )
    if created:
        sync_owner_pi_data.apply_async((owner.pk,), priority=3)
        messages.success(request, f"{char.character_name} added — sync running in the background.")
    elif owner.user == request.user:
        messages.info(request, f"{char.character_name} is already registered to your account.")
    else:
        messages.warning(request, f"{char.character_name} is registered to a different account.")
    return redirect("aa_pi_tracker:index")


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def remove_character(request):
    owner_pk = request.POST.get("owner_pk")
    if not owner_pk:
        return JsonResponse({"ok": False, "error": "Missing owner_pk."}, status=400)
    deleted, _ = PiOwner.objects.filter(pk=owner_pk, user=request.user).delete()
    if not deleted:
        return JsonResponse({"ok": False, "error": "Character not found."}, status=404)
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def trigger_sync(request):
    for owner in get_owners(request.user):
        sync_owner_pi_data.apply_async((owner.pk,), priority=3)
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def trigger_price_sync(request):
    sync_market_prices.apply_async(priority=3)
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_pi_tracker.view_pi")
def characters_page(request):
    owners = get_owners(request.user)
    owners_info = [
        {
            "owner": o,
            "planet_count": o.planet_count_ann,
            "last_sync": o.last_synced,
            "ic_level": o.interplanetary_consolidation,
            "ic_trained": o.interplanetary_consolidation_trained,
            "ccu_level": o.command_center_upgrades,
            "ccu_trained": o.command_center_upgrades_trained,
            "planetology": o.planetology,
            "planetology_trained": o.planetology_trained,
            "advanced_planetology": o.advanced_planetology,
            "advanced_planetology_trained": o.advanced_planetology_trained,
            "remote_sensing": o.remote_sensing,
            "remote_sensing_trained": o.remote_sensing_trained,
            "max_planets": o.max_planets,
        }
        for o in owners
    ]
    ctx = {
        "active_page": "characters",
        "owners_info": owners_info,
        **nav_data(request, owners),
    }
    return render(request, "aa_pi_tracker/view/characters.html", ctx)
