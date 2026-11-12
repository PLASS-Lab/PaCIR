"""Sound generalized exclusions using supported-value matching certificates."""

from time import perf_counter

from engine import Limits, Limited, Result
from engine_hall import HallQuery
from identity_filter import filter_alldifferent


class CertificateQuery(HallQuery):
    def search(self, selector, wanted, label):
        while self.solve(selector):
            risk, _ = self.inspect(label)
            if risk == wanted:
                return True
            positive = {v for v in self.solver.get_model() if v > 0}
            activity = [u if u in positive else -u for u in self.occ.values()]
            domains = {e: frozenset(a for a, z in self.z[e].items() if z in positive)
                       for e, u in self.occ.items() if u in positive}
            if not risk:
                filtered = filter_alldifferent(domains)
                evidence = set()
                for e, values in filtered.supported.items():
                    for a in sorted(values)[:self.problem.k + 1]:
                        residual = {other: candidates - {a} for other, candidates in domains.items() if other != e}
                        witness = filter_alldifferent(residual)
                        if not witness.feasible:
                            raise AssertionError("supported edge has no forced matching")
                        evidence.add(self.z[e][a])
                        evidence.update(self.z[other][v] for other, v in witness.matching.items())
                        self.stats["certificate_matchings"] = self.stats.get("certificate_matchings", 0) + 1
                self.stats["certificate_edges"] = self.stats.get("certificate_edges", 0) + len(evidence)
                # Any graph containing these full matchings remains non-risky.
                pattern = [*activity, *sorted(evidence)]
            else:
                # Any feasible subgraph of this risky graph remains risky.
                pattern = [*activity, *[-z for e in domains for z in self.z[e].values() if z not in positive]]
            self.add([-selector, *[-literal for literal in pattern]])
            self.blocks += 1
        return False


def evaluate_prefix(problem, t, *, scope="occupied_targets", limits=None, compress=True, symmetry=True):
    if type(t) is not int or not 0 <= t <= len(problem.fragments):
        raise ValueError("invalid prefix")
    if scope not in {"occupied_targets", "known_targets"}:
        raise ValueError("invalid scope")
    if type(compress) is not bool or type(symmetry) is not bool:
        raise ValueError("optimization switches must be boolean")
    started = perf_counter()
    query = CertificateQuery(problem, t, scope, limits or Limits(), compress, symmetry)
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
