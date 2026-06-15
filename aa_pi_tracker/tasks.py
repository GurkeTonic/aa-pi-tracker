"""Celery tasks: PI data sync and market prices.

ESI access goes through the django-esi OpenAPI client (see ``providers/esi.py``),
which transparently handles caching, ETags, the floating-window rate limit, the
global error limit, the User-Agent and the compatibility date. Planet, system
and type names are resolved from the local EVE SDE (``eve_sde``) to avoid extra
ESI calls. Market prices come from the third-party Fuzzwork API (not ESI).
"""

# Standard Library
from decimal import Decimal, InvalidOperation

# Third Party
import requests
from celery import shared_task

# Django
from django.core.cache import cache
from django.db import connection, transaction
from django.utils import timezone as djtimezone

# Alliance Auth
from allianceauth.services.hooks import get_extension_logger
from allianceauth.services.tasks import QueueOnce
from esi.exceptions import (
    ESIBucketLimitException,
    ESIErrorLimitException,
    HTTPNotModified,
)

from .app_settings import (
    AA_PI_TRACKER_EXPIRY_WARN_HOURS,
    AA_PI_TRACKER_MAINT_LOG_RETENTION_DAYS,
)
from .models import (
    PiExtractorPin,
    PiFactoryPin,
    PiMaintenanceLog,
    PiMarketPrice,
    PiOwner,
    PiPlanet,
    PiProjectPlanet,
    PiStorageItem,
)
from .pi_data import ESI_SCHEMATIC_NAMES, P0_TYPES, SCHEMATICS
from .providers.esi import (
    SKILL_ADVANCED_PLANETOLOGY,
    SKILL_COMMAND_CENTER_UPGRADES,
    SKILL_INTERPLANETARY_CONSOLIDATION,
    SKILL_PLANETOLOGY,
    SKILL_REMOTE_SENSING,
    esi,
    fetch_pi_skills,
    get_skills_token,
    get_token,
    parse_dt,
    user_agent,
)

logger = get_extension_logger(__name__)

FUZZWORK_URL = "https://market.fuzzwork.co.uk/aggregates/"
JITA_STATION_ID = 60003760

# Transient ESI limits — let Celery retry with backoff instead of failing.
ESI_RETRY = {
    "autoretry_for": (ESIErrorLimitException, ESIBucketLimitException),
    "retry_backoff": 30,
    "retry_kwargs": {"max_retries": 3},
}


def _get_product_name(type_id: int, extra_names: dict | None = None) -> str:
    name = P0_TYPES.get(type_id)
    if name:
        return name
    if extra_names and type_id in extra_names:
        return extra_names[type_id]
    return f"Type {type_id}"


def _populate_planet_location(planet_obj: PiPlanet) -> None:
    """Fill planet name + system/region info from SDE — zero ESI calls."""
    try:
        # Third Party
        from eve_sde.models import Planet as SDEPlanet

        sde = SDEPlanet.objects.select_related(
            "solar_system__constellation__region"
        ).get(id=planet_obj.planet_id)
        ss = sde.solar_system
        update_fields = [
            "solar_system_id",
            "solar_system_name",
            "security_status",
            "constellation_name",
            "region_name",
        ]
        planet_obj.solar_system_id = ss.id
        planet_obj.solar_system_name = ss.name
        planet_obj.security_status = ss.security_status
        planet_obj.constellation_name = ss.constellation.name
        planet_obj.region_name = ss.constellation.region.name
        if not planet_obj.planet_name:
            planet_obj.planet_name = sde.name
            update_fields.append("planet_name")
        planet_obj.save(update_fields=update_fields)
    except Exception as exc:
        logger.warning("SDE lookup failed for planet %s: %s", planet_obj.planet_id, exc)


# ── PI data sync ───────────────────────────────────────────────────────────────


@shared_task(base=QueueOnce, once={"graceful": True})
def sync_all_pi_data():
    try:
        for owner in PiOwner.objects.all():
            sync_owner_pi_data.apply_async((owner.pk,), priority=3)
    except Exception:
        logger.exception("sync_all_pi_data: failed to fan out PI sync tasks")


@shared_task(base=QueueOnce, once={"graceful": True}, **ESI_RETRY)
def sync_owner_pi_data(owner_pk: int):
    try:
        owner = PiOwner.objects.get(pk=owner_pk)
    except PiOwner.DoesNotExist:
        return

    char_id = owner.character.character_id
    token = get_token(char_id)
    if not token:
        logger.warning("No valid token for PI owner %s", owner)
        return

    # Planet list. A 304 means the colonies are unchanged since the last sync;
    # the pin details only change when a colony is modified (which also bumps
    # this list's last-modified), so we can safely skip the per-planet refresh.
    planets_changed = True
    planet_list = []
    try:
        planet_list = esi.client.Planetary_Interaction.GetCharactersCharacterIdPlanets(
            character_id=char_id, token=token
        ).results()
    except HTTPNotModified:
        planets_changed = False
    except (ESIErrorLimitException, ESIBucketLimitException):
        raise
    except Exception as e:
        logger.error("Failed to fetch planets for %s: %s", owner, e)
        return

    # Skills live on a separate endpoint with its own cache; refresh regardless.
    owner.last_synced = djtimezone.now()
    owner_update_fields = ["last_synced"]
    skills_token = get_skills_token(char_id)
    if skills_token:
        skill_levels = fetch_pi_skills(char_id, skills_token)
        if skill_levels is not None:
            _skill_map = {
                SKILL_INTERPLANETARY_CONSOLIDATION: (
                    "interplanetary_consolidation",
                    "interplanetary_consolidation_trained",
                ),
                SKILL_COMMAND_CENTER_UPGRADES: (
                    "command_center_upgrades",
                    "command_center_upgrades_trained",
                ),
                SKILL_PLANETOLOGY: ("planetology", "planetology_trained"),
                SKILL_ADVANCED_PLANETOLOGY: (
                    "advanced_planetology",
                    "advanced_planetology_trained",
                ),
                SKILL_REMOTE_SENSING: ("remote_sensing", "remote_sensing_trained"),
            }
            for skill_id, (active_field, trained_field) in _skill_map.items():
                active, trained = skill_levels.get(skill_id, (0, 0))
                setattr(owner, active_field, active)
                setattr(owner, trained_field, trained)
                owner_update_fields.extend([active_field, trained_field])

    owner.save(update_fields=owner_update_fields)

    if not planets_changed:
        return

    existing_ids = set(owner.planets.values_list("planet_id", flat=True))

    for p in planet_list:
        planet_id = p.planet_id
        planet_obj, created = PiPlanet.objects.update_or_create(
            owner=owner,
            planet_id=planet_id,
            defaults={
                "planet_type": getattr(p, "planet_type", "barren") or "barren",
                "upgrade_level": getattr(p, "upgrade_level", 0) or 0,
                "last_update": parse_dt(getattr(p, "last_update", None)),
            },
        )
        existing_ids.discard(planet_id)
        if created or not planet_obj.solar_system_name:
            _populate_planet_location(planet_obj)
        _sync_planet_pins(planet_obj, char_id, token)

    if existing_ids:
        owner.planets.filter(planet_id__in=existing_ids).delete()

    _try_link_project_planets(owner)


def _try_link_project_planets(owner: PiOwner) -> None:
    """Auto-link planned PiProjectPlanet slots to newly synced PiPlanet objects.

    Matches on planned_char_id + planned_planet_type + planned_system_name.
    Only links when the match is unambiguous (exactly one candidate for that key).
    Slots without a planned_system_name are skipped — the optimizer did not suggest
    a specific system, so there is nothing to match against.
    """
    # Standard Library
    from collections import defaultdict

    char_id = owner.character.character_id

    unlinked = list(
        PiProjectPlanet.objects.filter(
            planet__isnull=True,
            planned_char_id=char_id,
            planned_system_name__gt="",
        )
    )
    if not unlinked:
        return

    already_linked_ids = set(
        PiProjectPlanet.objects.filter(planet__isnull=False).values_list(
            "planet_id", flat=True
        )
    )

    candidates = [
        p
        for p in owner.planets.all()
        if p.pk not in already_linked_ids and p.solar_system_name
    ]

    by_type_system: dict = defaultdict(list)
    for p in candidates:
        by_type_system[(p.planet_type, p.solar_system_name)].append(p)

    for pp in unlinked:
        key = (pp.planned_planet_type, pp.planned_system_name)
        matches = by_type_system.get(key, [])
        if len(matches) == 1:
            pp.planet = matches[0]
            pp.save(update_fields=["planet"])
            by_type_system[key] = []
            logger.info(
                "Auto-linked planned slot pk=%s (project=%s, role=%s) → planet %s",
                pp.pk,
                pp.project_id,
                pp.role,
                matches[0],
            )


def _sync_planet_pins(planet: PiPlanet, char_id: int, token):
    try:
        data = esi.client.Planetary_Interaction.GetCharactersCharacterIdPlanetsPlanetId(
            character_id=char_id, planet_id=planet.planet_id, token=token
        ).result()
    except HTTPNotModified:
        return  # pins unchanged — keep what we have
    except (ESIErrorLimitException, ESIBucketLimitException):
        raise
    except Exception as e:
        logger.error("Failed to fetch pins for planet %s: %s", planet, e)
        return

    pins = getattr(data, "pins", None) or []

    # Preserve the expiry-notification dedup flag across the delete+recreate below.
    # Keyed by (product, expiry_time): a still-running program keeps its flag, a
    # newly installed program (different expiry_time) starts fresh (un-notified).
    prev_notified = {
        (e.product_type_id, e.expiry_time): e.notified_expiry
        for e in planet.extractors.all()
    }

    # Batch SDE lookup for all type_ids not in P0_TYPES
    unknown_ids = set()
    for pin in pins:
        ext = getattr(pin, "extractor_details", None)
        product_type_id = getattr(ext, "product_type_id", None) if ext else None
        if product_type_id and product_type_id not in P0_TYPES:
            unknown_ids.add(product_type_id)
        for item in getattr(pin, "contents", None) or []:
            tid = getattr(item, "type_id", None)
            if tid and tid not in P0_TYPES:
                unknown_ids.add(tid)
    sde_names: dict[int, str] = {}
    if unknown_ids:
        try:
            # Third Party
            from eve_sde.models import ItemType

            sde_names = dict(
                ItemType.objects.filter(id__in=unknown_ids).values_list("id", "name")
            )
        except Exception:
            pass

    extractors = []
    factories = []
    storage_totals: dict[int, int] = {}

    for pin in pins:
        ext = getattr(pin, "extractor_details", None)
        product_type_id = getattr(ext, "product_type_id", None) if ext else None
        schematic_id = getattr(pin, "schematic_id", None)

        if product_type_id:
            expiry = parse_dt(getattr(pin, "expiry_time", None))
            extractors.append(
                PiExtractorPin(
                    planet=planet,
                    product_type_id=product_type_id,
                    product_name=_get_product_name(product_type_id, sde_names),
                    cycle_time=getattr(ext, "cycle_time", 1800) or 1800,
                    qty_per_cycle=getattr(ext, "qty_per_cycle", 0) or 0,
                    head_count=len(getattr(ext, "heads", None) or []),
                    expiry_time=expiry,
                    install_time=parse_dt(getattr(pin, "install_time", None)),
                    last_cycle_start=parse_dt(getattr(pin, "last_cycle_start", None)),
                    notified_expiry=prev_notified.get((product_type_id, expiry), False),
                )
            )
        elif schematic_id:
            factories.append(
                PiFactoryPin(
                    planet=planet,
                    schematic_id=schematic_id,
                    schematic_name=ESI_SCHEMATIC_NAMES.get(
                        schematic_id, f"Schematic {schematic_id}"
                    ),
                )
            )

        for item in getattr(pin, "contents", None) or []:
            tid = getattr(item, "type_id", None)
            amt = getattr(item, "amount", 0) or 0
            if tid and amt:
                storage_totals[tid] = storage_totals.get(tid, 0) + amt

    with transaction.atomic():
        planet.extractors.all().delete()
        planet.factories.all().delete()
        planet.storage_items.all().delete()
        if extractors:
            PiExtractorPin.objects.bulk_create(extractors)
        if factories:
            PiFactoryPin.objects.bulk_create(factories)
        if storage_totals:
            items = [
                PiStorageItem(
                    planet=planet,
                    type_id=tid,
                    type_name=_get_product_name(tid, sde_names),
                    amount=amt,
                )
                for tid, amt in storage_totals.items()
            ]
            PiStorageItem.objects.bulk_create(items)


# ── Market price sync ──────────────────────────────────────────────────────────


@shared_task(base=QueueOnce, once={"graceful": True})
def sync_market_prices():
    """Fetch Jita buy prices for all PI products from Fuzzwork market API."""
    cache_key = "pi_tracker_market_prices"
    if cache.get(cache_key) is not None:
        logger.debug("Market prices still cached, skipping Fuzzwork call")
        return

    # Third Party
    from eve_sde.models import ItemType

    type_map: dict[int, tuple[str, int]] = {}

    schematic_names = list(SCHEMATICS.keys())
    sde_types = {
        t.name: t.id
        for t in ItemType.objects.filter(name__in=schematic_names).only("id", "name")
    }
    for schematic_name, data in SCHEMATICS.items():
        tier = data["tier"]
        type_id = sde_types.get(schematic_name)
        if type_id:
            type_map[type_id] = (schematic_name, tier)
        else:
            logger.warning("PI product not found in SDE: %s", schematic_name)

    if not type_map:
        logger.warning("No PI type IDs to price, aborting market sync")
        return

    type_ids_str = ",".join(str(tid) for tid in sorted(type_map.keys()))
    try:
        resp = requests.get(
            FUZZWORK_URL,
            params={"types": type_ids_str, "station": JITA_STATION_ID},
            headers={"User-Agent": user_agent()},
            timeout=30,
        )
        resp.raise_for_status()
        price_data = resp.json()
    except Exception as exc:
        logger.error("Fuzzwork market API failed: %s", exc)
        return

    items_to_upsert = []
    for type_id_str, prices in price_data.items():
        type_id = int(type_id_str)
        if type_id not in type_map:
            continue
        name, tier = type_map[type_id]
        try:
            jita_buy = Decimal(str((prices.get("buy") or {}).get("max") or 0)).quantize(
                Decimal("0.01")
            )
        except (InvalidOperation, ValueError):
            jita_buy = Decimal("0")
        items_to_upsert.append(
            PiMarketPrice(type_id=type_id, type_name=name, tier=tier, jita_buy=jita_buy)
        )

    if items_to_upsert:
        # AA runs on MySQL/MariaDB, which do the upsert but cannot name the
        # conflict target — passing unique_fields there raises NotSupportedError.
        # Set it only on backends that require it (e.g. SQLite in tests) so the
        # bulk_create stays portable.
        upsert_kwargs = {
            "update_conflicts": True,
            "update_fields": ["type_name", "tier", "jita_buy"],
        }
        if connection.features.supports_update_conflicts_with_target:
            upsert_kwargs["unique_fields"] = ["type_id"]
        PiMarketPrice.objects.bulk_create(items_to_upsert, **upsert_kwargs)

    cache.set(cache_key, True, timeout=1800)
    logger.info(
        "PI market prices updated for %d products (Jita buy)", len(items_to_upsert)
    )


# ── Extractor expiry notifications ───────────────────────────────────────────────


@shared_task(base=QueueOnce, once={"graceful": True})
def check_extractor_expiry():
    """Warn each owner in-app (AA notification bell) when an extractor program is
    about to run dry. One notification per user, summarizing all their expiring
    extractors. Each pin is flagged afterwards so it is not re-notified; the flag
    survives a re-sync and resets only when a new program is installed
    (see ``_sync_planet_pins``)."""
    # Standard Library
    from collections import defaultdict
    from datetime import timedelta

    # Alliance Auth
    from allianceauth.notifications import notify

    now = djtimezone.now()
    threshold = now + timedelta(hours=AA_PI_TRACKER_EXPIRY_WARN_HOURS)
    pins = list(
        PiExtractorPin.objects.filter(
            notified_expiry=False,
            expiry_time__isnull=False,
            expiry_time__lte=threshold,
        ).select_related("planet__owner__user", "planet__owner__character")
    )
    if not pins:
        return

    by_user: dict = defaultdict(list)
    for pin in pins:
        owner = pin.planet.owner
        user = getattr(owner, "user", None)
        if user:
            by_user[user].append(pin)

    for user, user_pins in by_user.items():
        lines = []
        for p in sorted(user_pins, key=lambda x: x.expiry_time):
            remaining = p.expiry_time - now
            if remaining.total_seconds() <= 0:
                when = "expired"
            else:
                hours = int(remaining.total_seconds() // 3600)
                when = f"in {hours}h" if hours else "< 1h"
            lines.append(
                f"• {p.planet.planet_name}: {p.product_name or 'Extractor'} ({when})"
            )
        title = f"PI: {len(user_pins)} extractor program(s) expiring soon"
        notify(user, title, message="\n".join(lines), level="warning")

    PiExtractorPin.objects.filter(pk__in=[p.pk for p in pins]).update(
        notified_expiry=True
    )


# ── Maintenance log retention ────────────────────────────────────────────────────


@shared_task(base=QueueOnce, once={"graceful": True})
def purge_old_maintenance_logs():
    """Delete PiMaintenanceLog rows older than the retention window so the daily
    per-character progress table does not grow unbounded."""
    # Standard Library
    from datetime import timedelta

    cutoff = djtimezone.localdate() - timedelta(
        days=AA_PI_TRACKER_MAINT_LOG_RETENTION_DAYS
    )
    deleted, _ = PiMaintenanceLog.objects.filter(date__lt=cutoff).delete()
    if deleted:
        logger.info("Purged %d maintenance log(s) older than %s", deleted, cutoff)
