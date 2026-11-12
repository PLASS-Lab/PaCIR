"""Problem definitions and bounded reference enumeration."""

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import product
from math import prod
from types import MappingProxyType

from identity_filter import filter_alldifferent


@dataclass(frozen=True)
class Fragment:
    support: frozenset[str]
    domain: frozenset[str]

    def __post_init__(self):
        object.__setattr__(self, "support", frozenset(self.support))
        object.__setattr__(self, "domain", frozenset(self.domain))


@dataclass(frozen=True)
class Problem:
    universe: frozenset[str]
    slots: tuple[str, ...]
    anchors: Mapping[str, frozenset[str]]
    fragments: tuple[Fragment, ...]
    k: int = 1
    must_links: tuple[tuple[int, int], ...] = ()
    cannot_links: tuple[tuple[int, int], ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "universe", frozenset(self.universe))
        object.__setattr__(self, "slots", tuple(self.slots))
        object.__setattr__(self, "fragments", tuple(self.fragments))
        object.__setattr__(self, "anchors", MappingProxyType({
            e: frozenset(values) for e, values in self.anchors.items()
        }))
        for field in ("must_links", "cannot_links"):
            object.__setattr__(self, field, tuple(tuple(p) for p in getattr(self, field)))
        if not self.universe or not self.slots or len(set(self.slots)) != len(self.slots):
            raise ValueError("Nonempty universe and unique nonempty slots required")
        if any(not isinstance(x, str) or not x for x in (*self.universe, *self.slots)):
            raise ValueError("Identifiers must be nonempty strings")
        if type(self.k) is not int or self.k < 1:
            raise ValueError("K must be a positive integer")
        if set(self.anchors) != set(self.slots):
            raise ValueError("Exactly one initial domain per slot required")
        if any(not b or not b <= self.universe for b in self.anchors.values()):
            raise ValueError("Initial domains must be nonempty subsets of the universe")
        for f in self.fragments:
            if not f.support or not f.support <= self.universe:
                raise ValueError("Fragment support outside the input contract")
            if not f.domain or not f.domain <= set(self.slots):
                raise ValueError("Fragment association domain outside the input contract")
        for pair in self.must_links + self.cannot_links:
            if len(pair) != 2 or any(
                type(i) is not int or not 1 <= i <= len(self.fragments) for i in pair
            ):
                raise ValueError("Links use 1-based fragment indices")


@dataclass(frozen=True)
class Hypothesis:
    association: tuple[str, ...]
    candidates: dict[str, frozenset[str]]
    supported: dict[str, frozenset[str]]
    risk: bool
    removed_edges: int


@dataclass(frozen=True)
class PrefixResult:
    t: int
    verdict: str
    possible: bool | None
    certain: bool | None
    hypotheses: tuple[Hypothesis, ...]
    counts: dict[str, int]
    reason: str | None = None


@dataclass(frozen=True)
class StreamResult:
    prefixes: tuple[PrefixResult, ...]
    tau_possible: int | None
    tau_certain: int | None
    complete: bool
    certified_through: int


def evaluate_prefix(
    problem: Problem,
    t: int,
    *,
    scope: str = "known_targets",
    identity: str = "alldifferent",
    max_associations: int = 10_000,
) -> PrefixResult:
    """Enumerate hypotheses under the selected slot scope and identity rule."""
    if type(t) is not int or not 0 <= t <= len(problem.fragments):
        raise ValueError("Invalid prefix index")
    if scope not in {"known_targets", "occupied_targets"}:
        raise ValueError("Unknown target scope")
    if identity not in {"alldifferent", "local"}:
        raise ValueError("Unknown identity mode")
    if type(max_associations) is not int or max_associations < 1:
        raise ValueError("Positive association budget required")
    fragments = problem.fragments[:t]
    count = prod(len(f.domain) for f in fragments)
    counts = {"raw": count, "links_rejected": 0, "intersection_rejected": 0,
              "identity_rejected": 0, "surviving": 0, "removed_edges": 0}
    if count > max_associations:
        return PrefixResult(t, "UNKNOWN", None, None, (), counts, "association_budget")

    kept = []
    for association in product(*(sorted(f.domain) for f in fragments)):
        if any(
            i <= t and j <= t and association[i - 1] != association[j - 1]
            for i, j in problem.must_links
        ) or any(
            i <= t and j <= t and association[i - 1] == association[j - 1]
            for i, j in problem.cannot_links
        ):
            counts["links_rejected"] += 1
            continue
        active = problem.slots if scope == "known_targets" else tuple(
            e for e in problem.slots if e in association
        )
        candidates = {e: problem.anchors[e] for e in active}
        for f, e in zip(fragments, association):
            candidates[e] = candidates[e] & f.support
        if any(not values for values in candidates.values()):
            counts["intersection_rejected"] += 1
            continue
        removed = 0
        if identity == "alldifferent":
            filtered = filter_alldifferent(candidates)
            if not filtered.feasible:
                counts["identity_rejected"] += 1
                continue
            supported = filtered.supported
            removed = len(filtered.removed)
        else:
            supported = dict(candidates)
        risk = any(1 <= len(values) <= problem.k for values in supported.values())
        kept.append(Hypothesis(association, candidates, supported, risk, removed))
        counts["removed_edges"] += removed
    counts["surviving"] = len(kept)
    if not kept:
        return PrefixResult(t, "INCONSISTENT", False, False, (), counts)
    possible = any(h.risk for h in kept)
    certain = all(h.risk for h in kept)
    verdict = "ALERT" if certain else "DEFER" if possible else "SAFE"
    return PrefixResult(t, verdict, possible, certain, tuple(kept), counts)


def evaluate_stream(problem: Problem, **kwargs) -> StreamResult:
    prefixes = []
    tau_possible = tau_certain = None
    certified_through = -1
    for t in range(len(problem.fragments) + 1):
        result = evaluate_prefix(problem, t, **kwargs)
        prefixes.append(result)
        if result.verdict == "UNKNOWN":
            return StreamResult(tuple(prefixes), tau_possible, tau_certain, False,
                                certified_through)
        certified_through = t
        if result.possible and tau_possible is None:
            tau_possible = t
        if result.certain and tau_certain is None:
            tau_certain = t
    return StreamResult(tuple(prefixes), tau_possible, tau_certain, True,
                        certified_through)
