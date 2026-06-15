import math
from typing import Generator


# Dogma attribute 1683 / 1687 — defaults from dgmAttributeTypes
_DECAY_FACTOR = 0.012
_NOISE_FACTOR = 0.8


def calculate_extractor_values(
    total_cycles: int,
    cycle_time: int,
    qty_per_cycle: int,
) -> Generator[float, None, None]:
    """Yield the expected extraction output for each cycle.

    Follows the official CCP PI guide formula exactly.

    :param total_cycles: (expiry_time - install_time) / cycle_time
    :param cycle_time: cycle duration in seconds
    :param qty_per_cycle: base quantity from ESI extractor_details
    """
    bar_width = float(cycle_time) / 900.0
    phase_shift = pow(qty_per_cycle, 0.7)

    for cycle in range(total_cycles):
        t = (cycle + 0.5) * bar_width
        decay_value = qty_per_cycle / (1 + t * _DECAY_FACTOR)

        sin_a = math.cos(phase_shift + t * (1 / 12))
        sin_b = math.cos(phase_shift / 2 + t * 0.2)
        sin_c = math.cos(t * 0.5)
        sin_stuff = max((sin_a + sin_b + sin_c) / 3, 0)

        bar_height = decay_value * (1 + _NOISE_FACTOR * sin_stuff)
        yield math.floor(bar_width * bar_height)


def extractor_avg_per_hour(
    install_time,
    expiry_time,
    cycle_time: int,
    qty_per_cycle: int,
) -> float | None:
    """Return the full-program average extraction rate per hour.

    Matches EVE's in-game "average per hour" display. Returns None when
    inputs are missing or invalid.
    """
    if not install_time or not expiry_time or cycle_time <= 0 or qty_per_cycle <= 0:
        return None
    duration_s = (expiry_time - install_time).total_seconds()
    total_cycles = int(duration_s / cycle_time)
    if total_cycles <= 0:
        return None
    total = sum(calculate_extractor_values(total_cycles, cycle_time, qty_per_cycle))
    return total / (duration_s / 3600)
