"""Finite reference enumeration and symbolic-query checks."""

from collections import Counter
import itertools
from engine_exact_hall import evaluate_prefix
from monitor import Problem, Fragment
COUNTS = Counter()

def require(condition, message):
    if not condition:
        raise AssertionError(message)

def canonical(values):
    seen = {}
    return tuple(seen.setdefault(v, len(seen)) for v in values)



def accepts(labels, links):
    return all((labels[i] == labels[j]) == same for i, j, same in links)



def direct(supports, links=()):
    """Enumerate identity assignments to clues, then group by induced partition."""
    groups = {}
    for ids in itertools.product(*(sorted(s) for s in supports)):
        if not accepts(ids, links):
            continue
        labels = canonical(ids)
        supported = groups.setdefault(labels, [set() for _ in set(labels)])
        for label, candidate in zip(labels, ids):
            supported[label].add(candidate)
    return {labels: tuple(frozenset(s) for s in supported) for labels, supported in groups.items()}



def query(groups, k):
    if not groups:
        return 'INCONSISTENT', None, None
    risks = [any(1 <= len(s) <= k for s in supported) for supported in groups.values()]
    p, c = any(risks), all(risks)
    return 'ALERT' if c else 'DEFER' if p else 'SAFE', p, c



def extend(labels, amount, capacity):
    if not amount:
        yield labels
        return
    q = max(labels, default=-1)+1
    for value in range(q+(q < capacity)):
        yield from extend(labels+(value,), amount-1, capacity)



def partition_first(labels, supports, links, universe):
    """Independent block-first intersections and injective block assignments."""
    if not accepts(labels, links):
        return None
    raw = [set(universe) for _ in set(labels)]
    for label, support in zip(labels, supports):
        raw[label].intersection_update(support)
    supported = [set() for _ in raw]
    found = False
    for assignment in itertools.product(*(sorted(s) for s in raw)):
        if len(set(assignment)) != len(assignment):
            continue
        found = True
        for i, a in enumerate(assignment):
            supported[i].add(a)
    return tuple(frozenset(s) for s in supported) if found else None



def problem(universe, supports, links, k, capacity=None):
    m = max(1, min(len(supports), len(universe))) if capacity is None else capacity
    slots = tuple(f'e{i}' for i in range(m))
    return Problem(frozenset(universe), slots, {e: frozenset(universe) for e in slots},
        tuple(Fragment(frozenset(s), frozenset(slots)) for s in supports), k,
        tuple((i+1, j+1) for i, j, same in links if same),
        tuple((i+1, j+1) for i, j, same in links if not same))



def symbolic_check(universe, supports, links, k, expected=None, capacity=None):
    if expected is None:
        groups = direct(supports, links)
        if capacity is not None:
            groups = {key: value for key, value in groups.items() if len(value) <= capacity}
        expected = query(groups, k)
    for compress, symmetry in itertools.product((False, True), repeat=2):
        result = evaluate_prefix(problem(universe, supports, links, k, capacity), len(supports),
                                 scope='occupied_targets', compress=compress, symmetry=symmetry)
        actual = (result.verdict, result.possible, result.certain)
        if result.verdict == 'INCONSISTENT':
            actual = (result.verdict, None, None)
        require(actual == expected, f'query mismatch: {actual} != {expected}')
        COUNTS['symbolic_option_checks'] += 1



def exhaustive():
    universe = frozenset('abc')
    subsets = [frozenset(a for i, a in enumerate('abc') if mask & (1 << i)) for mask in range(1, 8)]
    pairs = tuple(itertools.combinations(range(3), 2))
    ordinal = 0
    for supports in itertools.product(subsets, repeat=3):
        for relations in itertools.product((None, False, True), repeat=3):
            links = tuple((i, j, kind) for (i, j), kind in zip(pairs, relations) if kind is not None)
            current = direct(supports, links)
            COUNTS['static_inputs'] += 1
            for staged in (False, True):
                old_links = tuple(edge for edge in links if edge[1] < 2) if staged else ()
                old = direct(supports[:2], old_links)
                rebuilt = {}
                for parent in old:
                    for labels in extend(parent, 1, len(universe)):
                        projected = partition_first(labels, supports, links, universe)
                        if projected is not None:
                            rebuilt[labels] = projected
                require(rebuilt == current, 'extension/reconstruction mismatch')
                COUNTS['update_rebuild_checks'] += 1
                for labels, supported in current.items():
                    prefix = labels[:2]
                    require(prefix in old, 'valid future has invalid past')
                    for i, before in enumerate(old[prefix]):
                        require(supported[i] <= before, 'supported identity grew on a surviving extension')
                        COUNTS['supported_inclusion_checks'] += 1
                for k in (1, 2, 3):
                    old_q, new_q = query(old, k), query(current, k)
                    if old and current:
                        require(not old_q[2] or new_q[2], 'certain risk decreased')
                    if not old:
                        require(not current, 'inconsistent input recovered without revision')
                    for supported in current.values():
                        y = any(len(s) <= k for s in supported)
                        require(new_q[0] != 'SAFE' or not y, 'false SAFE for feasible truth')
                        require(new_q[0] != 'ALERT' or y, 'false ALERT for feasible truth')
                        COUNTS['conditional_truth_checks'] += 1
                    COUNTS['temporal_K_checks'] += 1
            # Fixed caps can exclude additional feasible partitions, but cannot add them.
            for m in (1, 2, 3):
                restricted = {p: s for p, s in current.items() if len(s) <= m}
                for k in (1, 2, 3):
                    a, b = query(restricted, k), query(current, k)
                    if restricted:
                        require(not a[1] or b[1], 'possible lost when removing small cap')
                        require(not b[2] or a[2], 'certain gained when removing small cap')
                    COUNTS['capacity_inclusion_checks'] += 1
            if ordinal % 173 == 0:
                for k in (1, 2, 3):
                    symbolic_check(universe, supports, links, k, query(current, k))
            ordinal += 1

