from ..models import PiMarketPrice
from ..pi_data import PLANET_TYPE_SLUG_TO_P0


def known_p0(planet):
    for ext in planet.extractors.all():
        if ext.product_name:
            return ext.product_name
    return planet.user_resource or None


def possible_p0(planet):
    kp0 = known_p0(planet)
    if kp0:
        return {kp0}
    return set(PLANET_TYPE_SLUG_TO_P0.get(planet.planet_type, []))


def extraction_rate(planet):
    total = sum(e.qty_per_hour for e in planet.extractors.all() if e.product_name)
    return round(total, 0) if total > 0 else None


def planet_info(planet, jd=None):
    jumps = jd.get(planet.solar_system_id) if (jd and planet.solar_system_id) else None
    return {
        "pk": planet.pk,
        "name": planet.planet_name,
        "type": planet.planet_type,
        "type_display": planet.get_planet_type_display(),
        "char": planet.owner.character.character_name,
        "char_id": planet.owner.character.character_id,
        "system": planet.solar_system_name,
        "sec": planet.sec_display,
        "sec_class": planet.sec_class,
        "known_p0": known_p0(planet),
        "possible_p0": sorted(possible_p0(planet)),
        "rate": extraction_rate(planet),
        "upgrade_level": planet.upgrade_level,
        "jumps": jumps,
        "new_slot": False,
        "truly_missing": False,
    }


def market_prices():
    return {p.type_name: p.jita_buy for p in PiMarketPrice.objects.all()}
