from collections import deque

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


def _build_jump_graph():
    cached = cache.get("pi_tracker_jump_graph")
    if cached is not None:
        return cached
    from eve_sde.models import Stargate
    graph = {}
    for gate in Stargate.objects.values("solar_system_id", "destination_id"):
        src, dst = gate["solar_system_id"], gate["destination_id"]
        graph.setdefault(src, []).append(dst)
    cache.set("pi_tracker_jump_graph", graph, timeout=3600)
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


def jump_distances(home_system_id, max_jumps):
    """Return {system_id: jumps} for all systems within max_jumps of home."""
    return _bfs(home_system_id, max_jumps, _build_jump_graph())


def sde_types_in_range(jd):
    """
    Given {system_id: jumps}, return:
      available_slugs: set of planet type slugs that exist within range
      examples: {slug: (system_name, jumps)} — closest system per type
    Uses SDE data, not user-registered planets.
    """
    from eve_sde.models import Planet as SDEPlanet
    system_ids = list(jd.keys())
    rows = (
        SDEPlanet.objects
        .filter(solar_system_id__in=system_ids, item_type_id__in=SDE_TYPE_ID_TO_SLUG)
        .values("solar_system_id", "solar_system__name", "item_type_id")
    )
    available = set()
    examples = {}
    for row in rows:
        slug = SDE_TYPE_ID_TO_SLUG.get(row["item_type_id"])
        if not slug:
            continue
        available.add(slug)
        jumps = jd.get(row["solar_system_id"], 0)
        if slug not in examples or jumps < examples[slug][1]:
            examples[slug] = (row["solar_system__name"], jumps)
    return available, examples
