from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone as djtimezone
from django.utils.dateparse import parse_datetime

from allianceauth.services.hooks import get_extension_logger
from esi.models import Token

from .. import __version__

logger = get_extension_logger(__name__)

ESI_BASE = "https://esi.evetech.net"
ESI_HEADERS = {"X-Compatibility-Date": "2026-06-09"}

SKILL_INTERPLANETARY_CONSOLIDATION = 2495
SKILL_COMMAND_CENTER_UPGRADES = 2505
SKILL_PLANETOLOGY = 2406
SKILL_ADVANCED_PLANETOLOGY = 2403
SKILL_REMOTE_SENSING = 13279

_PI_SKILL_IDS = {
    SKILL_INTERPLANETARY_CONSOLIDATION,
    SKILL_COMMAND_CENTER_UPGRADES,
    SKILL_PLANETOLOGY,
    SKILL_ADVANCED_PLANETOLOGY,
    SKILL_REMOTE_SENSING,
}


def user_agent():
    email = getattr(settings, "ESI_USER_CONTACT_EMAIL", "unknown@example.com")
    return f"aa-pi-tracker/{__version__} ({email}; +https://github.com/GurkeTonic/aa-pi-tracker)"


def handle_resp(resp):
    remain = int(resp.headers.get("X-ESI-Error-Limit-Remain", 100))
    if remain <= 0:
        reset = resp.headers.get("X-ESI-Error-Limit-Reset", "?")
        logger.error("ESI error limit exhausted, resets in %ss — aborting", reset)
        raise RuntimeError(f"ESI error limit exhausted, resets in {reset}s")
    if remain < 10:
        logger.warning(
            "ESI error limit critical: %d remaining, resets in %ss",
            remain,
            resp.headers.get("X-ESI-Error-Limit-Reset", "?"),
        )
    if resp.status_code == 429:
        logger.warning("ESI 429, retry after %ss", resp.headers.get("Retry-After", "?"))
    resp.raise_for_status()


def cache_ttl(resp_headers):
    expires = resp_headers.get("Expires")
    if expires:
        try:
            exp_dt = parsedate_to_datetime(expires)
            return max(60, int(exp_dt.timestamp() - djtimezone.now().timestamp()))
        except Exception:
            pass
    return 300


def esi_get_auth(path, token):
    key = f"pi_tracker_auth_{token.character_id}_{path}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    resp = requests.get(
        f"{ESI_BASE}{path}",
        headers={
            **ESI_HEADERS,
            "Authorization": f"Bearer {token.valid_access_token()}",
            "User-Agent": user_agent(),
        },
        timeout=30,
    )
    handle_resp(resp)
    data = resp.json()
    cache.set(key, data, timeout=cache_ttl(resp.headers))
    return data


def get_token(character_id: int) -> Token | None:
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


def get_skills_token(character_id: int) -> Token | None:
    try:
        return (
            Token.objects.filter(
                character_id=character_id,
                scopes__name="esi-skills.read_skills.v1",
            )
            .require_valid()
            .first()
        )
    except Exception as e:
        logger.warning("Skills token error for char %s: %s", character_id, e)
        return None


def fetch_pi_skills(char_id: int, token: Token) -> dict | None:
    """Fetch PI skill levels. Returns {skill_id: (active_level, trained_level)}, None on error."""
    try:
        data = esi_get_auth(f"/v4/characters/{char_id}/skills", token)
    except Exception as e:
        logger.warning("Failed to fetch skills for char %s: %s", char_id, e)
        return None
    return {
        skill["skill_id"]: (
            skill.get("active_skill_level", 0),
            skill.get("trained_skill_level", 0),
        )
        for skill in data.get("skills", [])
        if skill.get("skill_id") in _PI_SKILL_IDS
    }


def parse_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return parse_datetime(str(value))
