from django import template

register = template.Library()


@register.filter
def isk(value):
    """Format a number as human-readable ISK (e.g. 1.23M, 450k)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if v == 0:
        return "0"
    if abs(v) >= 1_000_000_000:
        return f"{v / 1_000_000_000:.2f}B"
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"{v / 1_000:.1f}k"
    return f"{v:,.0f}"


@register.filter
def isk_per_hour(value):
    return f"{isk(value)}/h"


@register.filter
def filter_role(assignments, role):
    """Filter a list of planet assignment dicts by role field."""
    return [a for a in assignments if a.get("role", "") == role]


@register.filter
def skill_pips(level):
    """Return list of booleans [filled, ...] for 5 pip indicators."""
    lvl = int(level) if level is not None else 0
    return [i < lvl for i in range(5)]


@register.filter
def skill_pips_detailed(active, trained):
    """Return list of pip states for 5 pips: 'active', 'trained', or 'empty'.

    active  = active_skill_level (usable now, 0 on Alpha for Omega-only skills)
    trained = trained_skill_level (always reflects injected level)
    """
    a = int(active) if active is not None else 0
    t = int(trained) if trained is not None else a
    return [
        "active" if i < a else "trained" if i < t else "empty"
        for i in range(5)
    ]
