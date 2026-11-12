"""Exact existential Hall certificate for risk created by candidate filtering."""

from time import perf_counter

from engine import Limits, Limited, Result
from engine_certificates import CertificateQuery


class ExactHallQuery(CertificateQuery):
    def small_query(self, bound, label):
        selector = super().small_query(bound, label)
        if label != "potential_refined_risk":
            return selector
        self.stats["projection_risk_search"] = "tight_Hall_union_and_focal_residual"
        for e in self.problem.slots:
            outside = self.var(("hall_outside", e))
            residual = []
            for a, z in self.z[e].items():
                w = self.var(("hall_union", a))
                r = self.var(("hall_residual", e, a))
                self.add([-r, z])
                self.add([-r, -w])
                self.add([r, -z, w])
                residual.append(r)
            self.cardinality(residual, self.problem.k, "atmost", [-selector, -outside])
        return selector


def evaluate_prefix(problem, t, *, scope="occupied_targets", limits=None, compress=True, symmetry=True):
    if type(t) is not int or not 0 <= t <= len(problem.fragments):
        raise ValueError("invalid prefix")
    if scope not in {"occupied_targets", "known_targets"}:
        raise ValueError("invalid scope")
    if type(compress) is not bool or type(symmetry) is not bool:
        raise ValueError("optimization switches must be boolean")
    started = perf_counter()
    query = ExactHallQuery(problem, t, scope, limits or Limits(), compress, symmetry)
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
