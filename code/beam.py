"""Prefix-only Beam with exact rational scoring and matching support filtering."""

from dataclasses import dataclass
from fractions import Fraction
import identity_filter as identity


@dataclass(frozen=True)
class Hypothesis:
    labels: tuple
    raw: tuple
    supported: tuple
    score: Fraction


def project(domains):
    result = identity.filter_alldifferent({str(i): d for i, d in enumerate(domains)})
    return tuple(result.supported[str(i)] for i in range(len(domains))) if result.feasible else None


class Beam:
    def __init__(self, universe, width=1, k=1):
        self.universe = frozenset(universe)
        if not self.universe or any(not isinstance(a, str) for a in self.universe):
            raise ValueError('nonempty string candidate universe required')
        if type(width) is not int or width < 1 or type(k) is not int or k < 1:
            raise ValueError('positive integer width and K required')
        self.width, self.k = width, k
        self.supports, self.relations = (), frozenset()
        self.retained = (Hypothesis((), (), (), Fraction(0)),)
        self.margin = Fraction(1) if width == 1 else None
        self.time, self.terminal = 0, False

    def push(self, support=None, approved=()):
        support = None if support is None else frozenset(support)
        if support is not None and (not support or not support <= self.universe):
            raise ValueError('invalid support')
        supports = self.supports + (() if support is None else (support,))
        relations = set(self.relations)
        for i, j, kind in approved:
            if type(i) is not int or type(j) is not int or not 0 <= i < j < len(supports):
                raise ValueError('relation endpoints must be ordered and observed')
            if kind not in ('same', 'different'):
                raise ValueError('invalid relation kind')
            relations.add((i, j, kind))
        if self.terminal:
            raise ValueError('terminal Beam cannot resume')
        similarities = [Fraction(len(s & support), len(s | support)) for s in self.supports] if support is not None else []
        children, cache = {}, {}
        for parent in self.retained:
            labels_to_try = range(len(parent.raw) + 1) if support is not None else (None,)
            for label in labels_to_try:
                labels = parent.labels if label is None else parent.labels + (label,)
                if any((labels[i] == labels[j]) != (kind == 'same') for i, j, kind in relations):
                    continue
                raw = list(parent.raw)
                score = parent.score
                if label is not None:
                    if label == len(raw):
                        raw.append(support)
                    else:
                        raw[label] &= support
                    score += sum((q if old == label else 1-q for old, q in zip(parent.labels, similarities)), Fraction(0))
                raw = tuple(raw)
                if any(not d for d in raw):
                    continue
                if raw not in cache:
                    cache[raw] = project(raw)
                supported = cache[raw]
                if supported is not None:
                    children[labels] = Hypothesis(labels, raw, supported, score)
        ranked = sorted(children.values(), key=lambda h: (-h.score, h.labels))
        margin = self.margin
        if ranked and self.width == 1 and support is not None:
            gap = Fraction(1) if len(ranked) == 1 else (ranked[0].score-ranked[1].score)/max(1, len(supports)-1)
            margin = min(margin, gap)
        retained = tuple(ranked[:self.width])
        risks = [any(1 <= len(d) <= self.k for d in h.supported) for h in retained]
        top = 'BRANCH_FAILURE' if not retained else 'ALERT' if risks[0] else 'SAFE'
        consensus = 'BRANCH_FAILURE' if not retained else 'ALERT' if all(risks) else 'SAFE' if not any(risks) else 'ABSTAIN'
        self.supports, self.relations = supports, frozenset(relations)
        self.time += 1
        self.retained, self.margin, self.terminal = retained, margin, not bool(retained)
        return dict(event_time=self.time, clues=len(supports), verdict=top, consensus=consensus,
                    retained=[dict(labels=list(h.labels), sizes=[len(d) for d in h.supported], score=str(h.score)) for h in retained],
                    margin=None if margin is None else str(margin), candidates_before_pruning=len(ranked),
                    top_score_tied=len(ranked) > 1 and ranked[0].score == ranked[1].score)
