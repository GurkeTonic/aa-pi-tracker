from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone as djtimezone
from django.utils.dateparse import parse_datetime

from allianceauth.services.hooks import get_extension_logger
from esi.models import Token

from .models import PiExtractorPin, PiFactoryPin, PiOwner, PiPlanet
from .schematics import P0_TYPES

logger = get_extension_logger(__name__)

ESI_BASE = "https://esi.evetech.net"
ESI_HEADERS = {"X-Compatibility-Date": "2026-05-19"}


def _user_agent():
    email = getattr(settings, "ESI_USER_CONTACT_EMAIL", "unknown@example.com")
    return f"aa-pi-tracker/0.1.0 ({email}; +https://github.com/GurkeTonic/aa-pi-tracker)"


def _handle_resp(resp):
    remain = int(resp.headers.get("X-ESI-Error-Limit-Remain", 100))
    if remain <= 0:
        reset = resp.headers.get("X-ESI-Error-Limit-Reset", "?")
        logger.error("ESI error limit exhausted, resets in %ss — aborting", reset)
        resp.raise_for_status()
    if remain < 10:
        logger.warning(
            "ESI error limit critical: %d remaining, resets in %ss",
            remain,
            resp.headers.get("X-ESI-Error-Limit-Reset", "?"),
        )
    if resp.status_code == 429:
        logger.warning("ESI 429, retry after %ss", resp.headers.get("Retry-After", "?"))
    resp.raise_for_status()


def _cache_ttl(resp_headers):
    expires = resp_headers.get("Expires")
    if expires:
        try:
            exp_dt = parsedate_to_datetime(expires)
            return max(60, int(exp_dt.timestamp() - djtimezone.now().timestamp()))
        except Exception:
            pass
    return 300


def _esi_get_pub(path):
    key = f"pi_tracker_pub_{path}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    resp = requests.get(
        f"{ESI_BASE}{path}",
        headers={**ESI_HEADERS, "User-Agent": _user_agent()},
        timeout=30,
    )
    _handle_resp(resp)
    data = resp.json()
    cache.set(key, data, timeout=_cache_ttl(resp.headers))
    return data


def _esi_get_auth(path, token):
    key = f"pi_tracker_auth_{token.character_id}_{path}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    resp = requests.get(
        f"{ESI_BASE}{path}",
        headers={
            **ESI_HEADERS,
            "Authorization": f"Bearer {token.valid_access_token()}",
            "User-Agent": _user_agent(),
        },
        timeout=30,
    )
    _handle_resp(resp)
    data = resp.json()
    cache.set(key, data, timeout=_cache_ttl(resp.headers))
    return data


def _resolve_schematic_name(schematic_id: int) -> str:
    key = f"pi_tracker_schematic_{schematic_id}"
    cached = cache.get(key)
    if cached:
        return cached
    try:
        data = _esi_get_pub(f"/v1/universe/schematics/{schematic_id}")
        name = data.get("schematic_name", f"Schematic {schematic_id}")
    except Exception:
        name = f"Schematic {schematic_id}"
    cache.set(key, name, timeout=86400)
    return name


def _resolve_type_name(type_id: int) -> str:
    """Resolve any EVE type name from ESI, with 24h cache."""
    known = P0_TYPES.get(type_id)
    if known:
        return known
    key = f"pi_tracker_type_{type_id}"
    cached = cache.get(key)
    if cached:
        return cached
    try:
        data = _esi_get_pub(f"/v3/universe/types/{type_id}")
        name = data.get("name", f"Type {type_id}")
    except Exception:
        name = f"Type {type_id}"
    cache.set(key, name, timeout=86400)
    return name


def _get_token(character_id: int) -> Token | None:
    try:
        return (
            Token.objects.filter(
                character_id=character_id,
                scopes__name="esi-planets.manage_planets.v1",
            )
            .require_valid()
            .first()
        )
    except Exception as e:
        logger.warning("Token error for char %s: %s", character_id, e)
        return None


def _parse_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return parse_datetime(str(value))


@shared_task
def sync_all_pi_data():
    for owner in PiOwner.objects.all():
        sync_owner_pi_data.delay(owner.pk)


@shared_task
def sync_owner_pi_data(owner_pk: int):
    try:
        owner = PiOwner.objects.get(pk=owner_pk)
    except PiOwner.DoesNotExist:
        return

    char_id = owner.character.character_id
    token = _get_token(char_id)
    if not token:
        logger.warning("No valid token for PI owner %s", owner)
        return

    try:
        planet_list = _esi_get_auth(f"/v1/characters/{char_id}/planets", token)
    except Exception as e:
        logger.error("Failed to fetch planets for %s: %s", owner, e)
        return

    if not isinstance(planet_list, list):
        logger.error("Unexpected planet list response for %s: %r", owner, planet_list)
        return

    existing_ids = set(owner.planets.values_list("planet_id", flat=True))

    for p in planet_list:
        planet_id = p["planet_id"]
        planet_type = p.get("planet_type", "barren")
        upgrade_level = p.get("upgrade_level", 0)
        last_update = _parse_dt(p.get("last_update"))

        planet_obj, _ = PiPlanet.objects.update_or_create(
            owner=owner,
            planet_id=planet_id,
            defaults={
                "planet_type": planet_type,
                "upgrade_level": upgrade_level,
                "last_update": last_update,
            },
        )
        existing_ids.discard(planet_id)

        if not planet_obj.planet_name:
            try:
                name_data = _esi_get_pub(f"/v1/universe/planets/{planet_id}")
                planet_obj.planet_name = name_data.get("name", f"Planet {planet_id}")
                planet_obj.save(update_fields=["planet_name"])
            except Exception as e:
                logger.warning("Could not resolve planet name %s: %s", planet_id, e)

        _sync_planet_pins(planet_obj, char_id, token)

    if existing_ids:
        owner.planets.filter(planet_id__in=existing_ids).delete()


def _sync_planet_pins(planet: PiPlanet, char_id: int, token: Token):
    try:
        data = _esi_get_auth(
            f"/v3/characters/{char_id}/planets/{planet.planet_id}", token
        )
    except Exception as e:
        logger.error("Failed to fetch pins for planet %s: %s", planet, e)
        return

    pins = data.get("pins", []) if isinstance(data, dict) else []

    planet.extractors.all().delete()
    planet.factories.all().delete()

    extractors = []
    factories = []

    for pin in pins:
        ext = pin.get("extractor_details")
        schematic_id = pin.get("schematic_id")

        if ext and ext.get("product_type_id"):
            product_type_id = ext["product_type_id"]
            extractors.append(
                PiExtractorPin(
                    planet=planet,
                    product_type_id=product_type_id,
                    product_name=_resolve_type_name(product_type_id),
                    cycle_time=ext.get("cycle_time", 1800),
                    qty_per_cycle=ext.get("qty_per_cycle", 0),
                    expiry_time=_parse_dt(pin.get("expiry_time")),
                    install_time=_parse_dt(pin.get("install_time")),
                    last_cycle_start=_parse_dt(pin.get("last_cycle_start")),
                )
            )
        elif schematic_id:
            factories.append(
                PiFactoryPin(
                    planet=planet,
                    schematic_id=schematic_id,
                    schematic_name=_resolve_schematic_name(schematic_id),
                )
            )

    if extractors:
        PiExtractorPin.objects.bulk_create(extractors)
    if factories:
        PiFactoryPin.objects.bulk_create(factories)
