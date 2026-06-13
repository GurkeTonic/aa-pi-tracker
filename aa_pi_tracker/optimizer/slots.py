from django.db.models import Count, Prefetch

from ..models import PiOwner, PiPlanet, PiProjectPlanet


def get_char_slots(user=None, *, owners=None):
    """
    Per-char slot info. Pass either user (personal mode) or pre-fetched owners list (corp mode).
    """
    if owners is None:
        owners = list(
            PiOwner.objects.filter(user=user)
            .select_related("character")
            .prefetch_related(
                Prefetch("planets", queryset=PiPlanet.objects.prefetch_related("extractors"))
            )
        )

    user_ids = list({o.user_id for o in owners})
    char_ids = [o.character.character_id for o in owners]

    locked_pks = set(
        PiProjectPlanet.objects.filter(project__user__in=user_ids, planet__isnull=False)
        .values_list("planet_id", flat=True)
    )
    planned_per_char = {
        row["planned_char_id"]: row["cnt"]
        for row in (
            PiProjectPlanet.objects
            .filter(project__user__in=user_ids, planet__isnull=True, planned_char_id__in=char_ids)
            .exclude(planned_char_id=None)
            .values("planned_char_id")
            .annotate(cnt=Count("pk"))
        )
    }

    result = []
    for owner in owners:
        all_planets = list(owner.planets.all())
        free_colonized = [p for p in all_planets if p.pk not in locked_pks]
        locked_count = len(all_planets) - len(free_colonized)
        max_p = owner.max_planets or 6
        free_slots = max(0, max_p - locked_count)
        already_planned = planned_per_char.get(owner.character.character_id, 0)
        new_slots = max(0, free_slots - len(free_colonized) - already_planned)
        result.append({
            "owner": owner,
            "char_name": owner.character.character_name,
            "char_id": owner.character.character_id,
            "max_planets": max_p,
            "locked_count": locked_count,
            "free_slots": free_slots,
            "free_colonized": free_colonized,
            "new_slots": new_slots,
        })
    return result


def get_planet_pools(user=None, *, owners=None):
    """Planet pool summary for the optimizer page load."""
    from .planet_helpers import planet_info
    char_slots = get_char_slots(user, owners=owners)
    locked_count = sum(cs["locked_count"] for cs in char_slots)
    total_free_slots = sum(cs["free_slots"] for cs in char_slots)
    new_slots_count = sum(cs["new_slots"] for cs in char_slots)

    by_char = {}
    all_free = []
    for cs in char_slots:
        infos = [planet_info(p) for p in cs["free_colonized"]]
        all_free.extend(infos)
        if infos or cs["new_slots"] > 0:
            by_char[cs["char_name"]] = {
                "planets": infos,
                "new_slots": cs["new_slots"],
                "free_slots": cs["free_slots"],
            }

    return {
        "free": all_free,
        "free_count": len(all_free),
        "total_free_slots": total_free_slots,
        "new_slots_count": new_slots_count,
        "locked_count": locked_count,
        "by_char": by_char,
        "unknown_p0_count": sum(1 for i in all_free if not i["known_p0"]),
    }
