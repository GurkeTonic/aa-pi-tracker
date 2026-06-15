# Standard Library
import time
from collections import deque
from functools import lru_cache

# Django
from django.core.cache import cache

# SDE item_type_id → planet type slug for all standard PI planet types
SDE_TYPE_ID_TO_SLUG = {
    11: "temperate",
    12: "ice",
    13: "gas",
    2014: "oceanic",
    2015: "lava",
    2016: "barren",
    2017: "storm",
    2063: "plasma",
}


# Process-local memo for the jump graph: the full New Eden stargate graph
# (~14k edges) is expensive to (de)serialise from the shared cache on every
# optimizer request, so keep it in-process and only fall back to Redis/DB.
_LOCAL_GRAPH: dict = {"graph": None, "expires": 0.0}
_LOCAL_GRAPH_TTL = 3600


def _build_jump_graph():
    now = time.monotonic()
    if _LOCAL_GRAPH["graph"] is not None and now < _LOCAL_GRAPH["expires"]:
        return _LOCAL_GRAPH["graph"]
    graph = cache.get("pi_tracker_jump_graph")
    if graph is None:
        # Third Party
        from eve_sde.models import Stargate

        graph = {}
        for gate in Stargate.objects.values("solar_system_id", "destination_id"):
            graph.setdefault(gate["solar_system_id"], []).append(gate["destination_id"])
        cache.set("pi_tracker_jump_graph", graph, timeout=3600)
    _LOCAL_GRAPH["graph"] = graph
    _LOCAL_GRAPH["expires"] = now + _LOCAL_GRAPH_TTL
    return graph


def _bfs(center_id, max_jumps, graph):
    visited = {center_id: 0}
    queue = deque([(center_id, 0)])
    while queue:
        sys_id, jumps = queue.popleft()
        if jumps >= max_jumps:
            continue
        for nb in graph.get(sys_id, []):
            if nb not in visited:
                visited[nb] = jumps + 1
                queue.append((nb, jumps + 1))
    return visited


@lru_cache(maxsize=64)
def jump_distances(home_system_id, max_jumps):
    """Return {system_id: jumps} for all systems within max_jumps of home.

    Cached per (home, max_jumps) for the process lifetime — the graph is static
    SDE data, so the BFS result is stable. Callers treat the result as read-only.
    """
    return _bfs(home_system_id, max_jumps, _build_jump_graph())


def sde_types_in_range(jd):
    """
    Given {system_id: jumps}, return:
        available_slugs: set of planet type slugs that exist within range
        examples: {slug: (system_name, jumps, radius_km, planet_name)} —
        closest system per type; ties broken by smallest planet radius
    Uses SDE data, not user-registered planets.
    """
    # Third Party
    from eve_sde.models import Planet as SDEPlanet

    system_ids = list(jd.keys())
    rows = SDEPlanet.objects.filter(
        solar_system_id__in=system_ids, item_type_id__in=SDE_TYPE_ID_TO_SLUG
    ).values("solar_system_id", "solar_system__name", "item_type_id", "radius", "name")
    available = set()
    examples = {}
    for row in rows:
        slug = SDE_TYPE_ID_TO_SLUG.get(row["item_type_id"])
        if not slug:
            continue
        available.add(slug)
        jumps = jd.get(row["solar_system_id"], 0)
        radius_km = round(row["radius"] / 1000) if row.get("radius") else 999_000
        existing = examples.get(slug)
        if (
            existing is None
            or jumps < existing[1]
            or (jumps == existing[1] and radius_km < existing[2])
        ):
            examples[slug] = (row["solar_system__name"], jumps, radius_km, row["name"])
    return available, examples
