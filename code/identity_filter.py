"""AllDifferent support filtering via matching (Regin, 1994, Algorithms 1-2)."""

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class FilterResult:
    feasible: bool
    supported: dict[str, frozenset[str]]
    matching: dict[str, str]
    removed: frozenset[tuple[str, str]]
    hall_variables: frozenset[str] = frozenset()
    hall_values: frozenset[str] = frozenset()


def _components(graph: list[list[int]]) -> list[int]:
    """Strongly connected components via iterative Kosaraju."""
    reverse = [[] for _ in graph]
    for u, edges in enumerate(graph):
        for v in edges:
            reverse[v].append(u)
    visited: set[int] = set()
    order: list[int] = []
    for root in range(len(graph)):
        if root in visited:
            continue
        visited.add(root)
        stack = [(root, iter(graph[root]))]
        while stack:
            u, successors = stack[-1]
            v = next(successors, None)
            if v is None:
                order.append(u)
                stack.pop()
            elif v not in visited:
                visited.add(v)
                stack.append((v, iter(graph[v])))
    component = [-1] * len(graph)
    for root in reversed(order):
        if component[root] != -1:
            continue
        component[root] = root
        pending = [root]
        while pending:
            u = pending.pop()
            for v in reverse[u]:
                if component[v] == -1:
                    component[v] = root
                    pending.append(v)
    return component


def filter_alldifferent(domains: Mapping[str, Iterable[str]]) -> FilterResult:
    """Return supported values, or a Hall-deficiency witness if infeasible."""
    normalized = {u: frozenset(values) for u, values in domains.items()}
    if any(not isinstance(u, str) for u in normalized):
        raise ValueError("Variable identifiers must be strings")
    if any(not isinstance(v, str) for values in normalized.values() for v in values):
        raise ValueError("Candidate identifiers must be strings")
    variables = sorted(normalized)
    ordered = {u: sorted(normalized[u]) for u in variables}
    left: dict[str, str] = {}
    right: dict[str, str] = {}

    for root in variables:
        queue = deque([root])
        seen_left = {root}
        predecessor: dict[str, str] = {}
        free = None
        while queue and free is None:
            u = queue.popleft()
            for v in ordered[u]:
                if v in predecessor:
                    continue
                predecessor[v] = u
                if v not in right:
                    free = v
                    break
                other = right[v]
                if other not in seen_left:
                    seen_left.add(other)
                    queue.append(other)
        if free is None:
            return FilterResult(
                False,
                {u: frozenset() for u in variables},
                dict(left),
                frozenset((u, v) for u in variables for v in ordered[u]),
                frozenset(seen_left),
                frozenset(predecessor),
            )
        while free is not None:
            u = predecessor[free]
            previous = left.get(u)
            left[u] = free
            right[free] = u
            free = previous

    values = sorted(set().union(*normalized.values()) if normalized else set())
    variable_node = {u: i for i, u in enumerate(variables)}
    value_node = {v: len(variables) + i for i, v in enumerate(values)}
    graph: list[list[int]] = [[] for _ in range(len(variables) + len(values))]
    for u in variables:
        for v in ordered[u]:
            x, y = variable_node[u], value_node[v]
            source, target = (x, y) if left[u] == v else (y, x)
            graph[source].append(target)

    reachable = {value_node[v] for v in values if v not in right}
    queue = deque(sorted(reachable))
    while queue:
        for v in graph[queue.popleft()]:
            if v not in reachable:
                reachable.add(v)
                queue.append(v)
    component = _components(graph)

    # For an unmatched edge value -> variable, test the VALUE's reachability.
    supported = {
        u: frozenset(
            v for v in ordered[u]
            if left[u] == v
            or value_node[v] in reachable
            or component[variable_node[u]] == component[value_node[v]]
        )
        for u in variables
    }
    removed = frozenset(
        (u, v) for u in variables for v in normalized[u] - supported[u]
    )
    return FilterResult(True, supported, dict(left), removed)
