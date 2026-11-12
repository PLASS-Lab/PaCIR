"""Necessary Hall-set constraints for risk after candidate refinement."""

from time import perf_counter

from engine import Limits, Limited, Query, Result


class HallQuery(Query):
    def small_query(self, bound, label):
        if label != "potential_refined_risk":
            return super().small_query(bound, label)
        self.stats["projection_risk_search"] = "proper_active_tight_Hall_subset"
        selector = self.var(("query", label))
        selected, outside = {}, []
        for e in self.problem.slots:
            v = self.var(("hall_member", e))
            selected[e] = v
            self.add([-v, self.occ[e]])
            other = self.var(("hall_outside", e))
            outside.append(other)
            self.add([-other, self.occ[e]])
            self.add([-other, -v])
        self.add([-selector, *outside])
        members = list(selected.values())
        # The first local-risk query was UNSAT, so every active C has > K values.
        self.cardinality(members, self.problem.k + 1, "atleast", [-selector])
        union = []
        for a in self.assets:
            w = self.var(("hall_union", a))
            union.append(w)
            for e in self.problem.slots:
                z = self.z[e].get(a)
                if z is not None:
                    self.add([-selected[e], -z, w])
        # |N(J)| <= |J|; base matching feasibility supplies the reverse inequality.
        self.cardinality([*union, *[-v for v in members]], len(members), "atmost", [-selector])
        return selector


def evaluate_prefix(problem, t, *, scope="occupied_targets", limits=None, compress=True, symmetry=True):
    if type(t) is not int or not 0 <= t <= len(problem.fragments):
        raise ValueError("invalid prefix")
    if scope not in {"occupied_targets", "known_targets"}:
        raise ValueError("invalid scope")
    if type(compress) is not bool or type(symmetry) is not bool:
        raise ValueError("optimization switches must be boolean")
    started = perf_counter()
    query = HallQuery(problem, t, scope, limits or Limits(), compress, symmetry)
    try:
        try:
            verdict, possible, certain = query.verdict()
            reason = None
        except Limited as exc:
            verdict, possible, certain, reason = "UNKNOWN", None, None, str(exc)
        return Result(t, verdict, possible, certain, reason,
                      {**query.metrics(), "seconds": perf_counter() - started})
    finally:
        query.close()
