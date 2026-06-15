"""ESI access for PI Tracker.

All ESI calls go through the django-esi OpenAPI client (``esi`` below), which
transparently handles caching, ETags, the floating-window rate limit, the
global error limit, the User-Agent and the compatibility date. The client is
filtered to the three operations this plugin uses to keep the loaded spec (and
memory) small. Construction is lazy — no network until the first ``.client``
access, so it is safe to build at import time.

Type, planet and system names are resolved from the local EVE SDE (``eve_sde``)
elsewhere to avoid extra ESI calls.
"""

# Standard Library
from datetime import datetime, timezone

# Django
from django.conf import settings
from django.utils.dateparse import parse_datetime

# Alliance Auth
from allianceauth.services.hooks import get_extension_logger
from esi.exceptions import HTTPNotModified
from esi.models import Token
from esi.openapi_clients import ESIClientProvider

from .. import (
    __app_name_useragent__,
    __esi_compatibility_date__,
    __github_url__,
    __version__,
)

logger = get_extension_logger(__name__)

esi = ESIClientProvider(
    compatibility_date=__esi_compatibility_date__,
    ua_appname=__app_name_useragent__,
    ua_version=__version__,
    ua_url=__github_url__,
    operations=[
        "GetCharactersCharacterIdPlanets",
        "GetCharactersCharacterIdPlanetsPlanetId",
        "GetCharactersCharacterIdSkills",
    ],
)

SCOPE_PLANETS = "esi-planets.manage_planets.v1"
SCOPE_SKILLS = "esi-skills.read_skills.v1"

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
    """User-Agent for the third-party Fuzzwork market API.

    Only used for the non-ESI Fuzzwork call; the django-esi client builds its
    own User-Agent (and pulls in ``ESI_USER_CONTACT_EMAIL``) for ESI requests.
    """
    email = getattr(settings, "ESI_USER_CONTACT_EMAIL", "unknown@example.com")
    return f"{__app_name_useragent__}/{__version__} ({email}; +{__github_url__})"


def get_token(character_id: int) -> Token | None:
    try:
        return (
            Token.objects.filter(character_id=character_id, scopes__name=SCOPE_PLANETS)
            .require_valid()
            .first()
        )
    except Exception as e:
        logger.warning("Token error for char %s: %s", character_id, e)
        return None


def get_skills_token(character_id: int) -> Token | None:
    try:
        return (
            Token.objects.filter(character_id=character_id, scopes__name=SCOPE_SKILLS)
            .require_valid()
            .first()
        )
    except Exception as e:
        logger.warning("Skills token error for char %s: %s", character_id, e)
        return None


def fetch_pi_skills(char_id: int, token: Token) -> dict | None:
    """Fetch PI skill levels via ESI.

    Returns ``{skill_id: (active_level, trained_level)}``. Returns ``None`` on
    error or when the data is unchanged (304) — in both cases the caller keeps
    the previously stored skill levels.
    """
    try:
        data = esi.client.Skills.GetCharactersCharacterIdSkills(
            character_id=char_id, token=token
        ).result()
    except HTTPNotModified:
        return None
    except Exception as e:
        logger.warning("Failed to fetch skills for char %s: %s", char_id, e)
        return None
    return {
        skill.skill_id: (
            getattr(skill, "active_skill_level", 0) or 0,
            getattr(skill, "trained_skill_level", 0) or 0,
        )
        for skill in (getattr(data, "skills", None) or [])
        if skill.skill_id in _PI_SKILL_IDS
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
