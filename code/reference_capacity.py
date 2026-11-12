"""Independent support calculation using candidate-class capacities."""

from functools import lru_cache

def project(domains):
    domains = tuple(frozenset(s) for s in domains)
    q = len(domains)
    groups = {}
    for a in set().union(*domains) if domains else set():
        mask = sum(1 << j for j, s in enumerate(domains) if a in s)
        groups.setdefault(mask, set()).add(a)
    masks = sorted(groups)
    capacities = tuple(len(groups[m]) for m in masks)

    @lru_cache(None)
    def feasible(remaining, caps):
        if not remaining:
            return True
        choices = [(j, [g for g, mask in enumerate(masks) if caps[g] and mask & (1 << j)])
                   for j in range(q) if remaining & (1 << j)]
        j, options = min(choices, key=lambda x: len(x[1]))
        for g in options:
            updated = list(caps)
            updated[g] -= 1
            if feasible(remaining ^ (1 << j), tuple(updated)):
                return True
        return False

    all_blocks = (1 << q) - 1
    if not feasible(all_blocks, capacities):
        return None
    supported = []
    for j in range(q):
        candidates = set()
        for g, mask in enumerate(masks):
            if mask & (1 << j):
                caps = list(capacities)
                caps[g] -= 1
                if feasible(all_blocks ^ (1 << j), tuple(caps)):
                    candidates.update(groups[mask])
        supported.append(frozenset(candidates))
    return tuple(supported)

