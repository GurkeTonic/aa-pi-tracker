import requests
from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone as djtimezone

from allianceauth.services.hooks import get_extension_logger

from .models import PiExtractorPin, PiFactoryPin, PiMarketPrice, PiOwner, PiPlanet, PiStorageItem
from .providers.esi import (
    SKILL_ADVANCED_PLANETOLOGY,
    SKILL_COMMAND_CENTER_UPGRADES,
    SKILL_INTERPLANETARY_CONSOLIDATION,
    SKILL_PLANETOLOGY,
    SKILL_REMOTE_SENSING,
    esi_get_auth,
    fetch_pi_skills,
    get_skills_token,
    get_token,
    parse_dt,
    user_agent,
)
from .pi_data import ESI_SCHEMATIC_NAMES, P0_TYPES, SCHEMATICS

logger = get_extension_logger(__name__)

FUZZWORK_URL = "https://market.fuzzwork.co.uk/aggregates/"
JITA_STATION_ID = 60003760


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
        from eve_sde.models import Planet as SDEPlanet
        sde = SDEPlanet.objects.select_related(
            "solar_system__constellation__region"
        ).get(id=planet_obj.planet_id)
        ss = sde.solar_system
        update_fields = [
            "solar_system_id", "solar_system_name", "security_status",
            "constellation_name", "region_name",
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

@shared_task
def sync_all_pi_data():
    try:
        for owner in PiOwner.objects.all():
            sync_owner_pi_data.apply_async((owner.pk,), priority=3)
    except Exception:
        logger.exception("sync_all_pi_data: failed to fan out PI sync tasks")


@shared_task
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

    try:
        planet_list = esi_get_auth(f"/v1/characters/{char_id}/planets", token)
    except Exception as e:
        logger.error("Failed to fetch planets for %s: %s", owner, e)
        return

    if not isinstance(planet_list, list):
        logger.error("Unexpected planet list response for %s: %r", owner, planet_list)
        return

    owner.last_synced = djtimezone.now()
    owner_update_fields = ["last_synced"]

    skills_token = get_skills_token(char_id)
    if skills_token:
        skill_levels = fetch_pi_skills(char_id, skills_token)
        if skill_levels is not None:
            _skill_map = {
                SKILL_INTERPLANETARY_CONSOLIDATION: ("interplanetary_consolidation", "interplanetary_consolidation_trained"),
                SKILL_COMMAND_CENTER_UPGRADES: ("command_center_upgrades", "command_center_upgrades_trained"),
                SKILL_PLANETOLOGY: ("planetology", "planetology_trained"),
                SKILL_ADVANCED_PLANETOLOGY: ("advanced_planetology", "advanced_planetology_trained"),
                SKILL_REMOTE_SENSING: ("remote_sensing", "remote_sensing_trained"),
            }
            for skill_id, (active_field, trained_field) in _skill_map.items():
                active, trained = skill_levels.get(skill_id, (0, 0))
                setattr(owner, active_field, active)
                setattr(owner, trained_field, trained)
                owner_update_fields.extend([active_field, trained_field])

    owner.save(update_fields=owner_update_fields)

    existing_ids = set(owner.planets.values_list("planet_id", flat=True))

    for p in planet_list:
        planet_id = p["planet_id"]
        planet_obj, created = PiPlanet.objects.update_or_create(
            owner=owner,
            planet_id=planet_id,
            defaults={
                "planet_type": p.get("planet_type", "barren"),
                "upgrade_level": p.get("upgrade_level", 0),
                "last_update": parse_dt(p.get("last_update")),
            },
        )
        existing_ids.discard(planet_id)
        if created or not planet_obj.solar_system_name:
            _populate_planet_location(planet_obj)
        _sync_planet_pins(planet_obj, char_id, token)

    if existing_ids:
        owner.planets.filter(planet_id__in=existing_ids).delete()


def _sync_planet_pins(planet: PiPlanet, char_id: int, token):
    try:
        data = esi_get_auth(
            f"/v3/characters/{char_id}/planets/{planet.planet_id}", token
        )
    except Exception as e:
        logger.error("Failed to fetch pins for planet %s: %s", planet, e)
        return

    pins = data.get("pins", []) if isinstance(data, dict) else []

    # Batch SDE lookup for all type_ids not in P0_TYPES
    unknown_ids = set()
    for pin in pins:
        ext = pin.get("extractor_details")
        if ext and ext.get("product_type_id"):
            tid = ext["product_type_id"]
            if tid not in P0_TYPES:
                unknown_ids.add(tid)
        for item in pin.get("contents", []):
            tid = item.get("type_id")
            if tid and tid not in P0_TYPES:
                unknown_ids.add(tid)
    sde_names: dict[int, str] = {}
    if unknown_ids:
        try:
            from eve_sde.models import ItemType
            sde_names = dict(ItemType.objects.filter(id__in=unknown_ids).values_list("id", "name"))
        except Exception:
            pass

    extractors = []
    factories = []
    storage_totals: dict[int, int] = {}

    for pin in pins:
        ext = pin.get("extractor_details")
        schematic_id = pin.get("schematic_id")

        if ext and ext.get("product_type_id"):
            product_type_id = ext["product_type_id"]
            extractors.append(
                PiExtractorPin(
                    planet=planet,
                    product_type_id=product_type_id,
                    product_name=_get_product_name(product_type_id, sde_names),
                    cycle_time=ext.get("cycle_time", 1800),
                    qty_per_cycle=ext.get("qty_per_cycle", 0),
                    head_count=len(ext.get("heads", [])),
                    expiry_time=parse_dt(pin.get("expiry_time")),
                    install_time=parse_dt(pin.get("install_time")),
                    last_cycle_start=parse_dt(pin.get("last_cycle_start")),
                )
            )
        elif schematic_id:
            factories.append(
                PiFactoryPin(
                    planet=planet,
                    schematic_id=schematic_id,
                    schematic_name=ESI_SCHEMATIC_NAMES.get(schematic_id, f"Schematic {schematic_id}"),
                )
            )

        for item in pin.get("contents", []):
            tid = item.get("type_id")
            amt = item.get("amount", 0)
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

@shared_task
def sync_market_prices():
    """Fetch Jita buy prices for all PI products from Fuzzwork market API."""
    cache_key = "pi_tracker_market_prices"
    if cache.get(cache_key) is not None:
        logger.debug("Market prices still cached, skipping Fuzzwork call")
        return

    from eve_sde.models import ItemType

    type_map: dict[int, tuple[str, int]] = {}

    schematic_names = list(SCHEMATICS.keys())
    sde_types = {t.name: t.id for t in ItemType.objects.filter(name__in=schematic_names).only("id", "name")}
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
        jita_buy = float((prices.get("buy") or {}).get("max") or 0)
        items_to_upsert.append(
            PiMarketPrice(type_id=type_id, type_name=name, tier=tier, jita_buy=jita_buy)
        )

    if items_to_upsert:
        PiMarketPrice.objects.bulk_create(
            items_to_upsert,
            update_conflicts=True,
            update_fields=["type_name", "tier", "jita_buy"],
            unique_fields=["type_id"],
        )

    cache.set(cache_key, True, timeout=1800)
    logger.info("PI market prices updated for %d products (Jita buy)", len(items_to_upsert))
