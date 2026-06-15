from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.utils import timezone

from allianceauth.services.hooks import get_extension_logger

from ..models import PiExtractorPin, PiFactoryPin, PiMarketPrice, PiOwner, PiPlanet, PiProject, PiStorageItem
from ..pi_data import P0_TO_P1, p0_rate_to_p1_rate

logger = get_extension_logger(__name__)


def fmt_cycle(seconds: int) -> str:
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


def fmt_remaining(expiry_time, now):
    """Return (display_str, urgency). urgency: expired | critical | warning | ok."""
    if expiry_time is None:
        return "—", "ok"
    total = (expiry_time - now).total_seconds()
    if total <= 0:
        return "EXPIRED", "expired"
    if total < 4 * 3600:
        h, m = int(total // 3600), int((total % 3600) // 60)
        return f"{h}h {m}m", "critical"
    if total < 24 * 3600:
        h, m = int(total // 3600), int((total % 3600) // 60)
        return f"{h}h {m}m", "warning"
    d, h = int(total // 86400), int((total % 86400) // 3600)
    return f"{d}d {h}h", "ok"


def sec_class(sec):
    if sec is None:
        return "secondary"
    if sec >= 0.45:
        return "success"
    if sec >= 0.0:
        return "warning"
    return "danger"


def sec_display(sec):
    if sec is None:
        return "?"
    return f"{max(sec, -1.0):.1f}"


def get_owners(user, prefetch_planets=False):
    qs = (
        PiOwner.objects.filter(user=user)
        .select_related("character")
        .annotate(planet_count_ann=Count("planets"))
    )
    if prefetch_planets:
        qs = qs.prefetch_related(
            Prefetch(
                "planets",
                queryset=PiPlanet.objects.prefetch_related(
                    "extractors",
                    "factories",
                    Prefetch("storage_items", queryset=PiStorageItem.objects.all()),
                    "project_links__project",
                ),
            )
        )
    return qs


def load_prices() -> dict[str, float]:
    return {p.type_name: float(p.jita_buy) for p in PiMarketPrice.objects.all()}


def nav_data(request, owners=None) -> dict:
    if owners is None:
        owners = get_owners(request.user)
    now = timezone.now()
    urgent = PiExtractorPin.objects.filter(
        planet__owner__in=owners,
        expiry_time__lt=now + timedelta(hours=4),
    ).count()
    return {
        "nav_urgent": urgent,
        "nav_char_count": owners.count(),
    }


def get_project_or_404(request, pk):
    """Return project owned by user OR corp project they participate in."""
    project = (
        PiProject.objects.filter(
            Q(pk=pk, user=request.user) |
            Q(pk=pk, is_corp_project=True, participants__user=request.user)
        )
        .distinct()
        .first()
    )
    if not project:
        raise Http404
    return project


def get_corp_owners(user):
    from django.db.models import Prefetch
    corp_id, _ = manager_corp_id(user)
    if not corp_id:
        return []
    return list(
        PiOwner.objects.filter(
            shared_with_corp=True,
            character__corporation_id=corp_id,
        )
        .select_related("character", "user")
        .prefetch_related(
            Prefetch("planets", queryset=PiPlanet.objects.prefetch_related("extractors").order_by("planet_name"))
        )
    )


def manager_corp_id(user):
    """Return (corp_id, corp_name) from the user's main character."""
    try:
        main = user.profile.main_character
        if main:
            return main.corporation_id, main.corporation_name
    except AttributeError:
        pass
    except Exception:
        logger.exception("Unexpected error reading main character for user %s", user)
    from allianceauth.eveonline.models import EveCharacter
    char = EveCharacter.objects.filter(character_ownership__user=user).order_by("character_id").first()
    if char:
        return char.corporation_id, char.corporation_name
    return None, ""


def compute_extractors(owners, prices: dict, now) -> list:
    extractors = []
    for owner in owners:
        for planet in owner.planets.all():
            for ext in planet.extractors.all():
                time_remaining, urgency = fmt_remaining(ext.expiry_time, now)
                progress = 0
                if ext.install_time and ext.expiry_time:
                    total_s = (ext.expiry_time - ext.install_time).total_seconds()
                    elapsed_s = (now - ext.install_time).total_seconds()
                    if total_s > 0:
                        progress = min(100, max(0, int(elapsed_s / total_s * 100)))
                qty_h = ext.avg_per_hour
                p1_name = P0_TO_P1.get(ext.product_name)
                p1_rate = p0_rate_to_p1_rate(qty_h)
                isk_h = p1_rate * prices.get(p1_name, 0.0) if p1_name else 0.0
                extractors.append({
                    "character": owner.character.character_name,
                    "char_id": owner.character.character_id,
                    "region": planet.region_name or "—",
                    "system": planet.solar_system_name or "—",
                    "sec_class": sec_class(planet.security_status),
                    "sec_display": sec_display(planet.security_status),
                    "planet_name": planet.planet_name,
                    "planet_type": planet.get_planet_type_display(),
                    "upgrade_level": planet.upgrade_level,
                    "product": ext.product_name,
                    "head_count": ext.head_count,
                    "progress": progress,
                    "urgency": urgency,
                    "time_remaining": time_remaining,
                    "expiry_time": ext.expiry_time,
                    "cycle_display": fmt_cycle(ext.cycle_time),
                    "qty_per_cycle": ext.qty_per_cycle,
                    "qty_per_hour": round(qty_h, 0),
                    "isk_per_hour": isk_h,
                })
    _urgency_order = {"expired": 0, "critical": 1, "warning": 2, "ok": 3}
    extractors.sort(key=lambda e: (
        _urgency_order.get(e["urgency"], 9),
        e["expiry_time"] or now.replace(year=9999),
    ))
    return extractors


def compute_planets(owners, prices: dict) -> list:
    all_planets = []
    for owner in owners:
        for planet in owner.planets.all():
            content_extractors = defaultdict(int)
            planet_isk_h = 0.0
            for ext in planet.extractors.all():
                if ext.product_name:
                    content_extractors[ext.product_name] += 1
                    p1_name = P0_TO_P1.get(ext.product_name)
                    p1_rate = p0_rate_to_p1_rate(ext.avg_per_hour)
                    planet_isk_h += p1_rate * prices.get(p1_name, 0.0) if p1_name else 0.0
            content_factories = defaultdict(int)
            for fac in planet.factories.all():
                if fac.schematic_name:
                    content_factories[fac.schematic_name] += 1
            storage = [
                {"name": s.type_name, "amount": s.amount,
                 "isk_value": s.amount * prices.get(s.type_name, 0)}
                for s in planet.storage_items.all()
            ]
            storage_isk_total = sum(s["isk_value"] for s in storage)
            all_planets.append({
                "owner": owner,
                "planet": planet,
                "region": planet.region_name or "—",
                "system": planet.solar_system_name or "—",
                "sec_class": sec_class(planet.security_status),
                "sec_display": sec_display(planet.security_status),
                "extractor_count": len(planet.extractors.all()),
                "factory_count": len(planet.factories.all()),
                "assigned_projects": [pp.project.name for pp in planet.project_links.all()],
                "content_extractors": dict(content_extractors),
                "content_factories": dict(content_factories),
                "isk_per_hour": planet_isk_h,
                "storage": sorted(storage, key=lambda x: -x["amount"]),
                "storage_isk_total": storage_isk_total,
            })
    all_planets.sort(key=lambda p: (p["region"], p["system"], p["planet"].planet_name))
    return all_planets
