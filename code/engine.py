"""SAT risk queries with bounded candidate multiplicities and matching support filtering."""

from collections import defaultdict
from dataclasses import asdict, dataclass
from math import prod
from time import perf_counter

from identity_filter import filter_alldifferent
from monitor import Problem
from pysat.card import CardEnc, EncType
from pysat.formula import IDPool
from pysat.solvers import Solver


@dataclass(frozen=True)
class Limits:
    variables: int = 500_000
    clauses: int = 2_000_000
    conflicts: int = 100_000
    refinements: int = 1_000

    def __post_init__(self):
        if any(type(v) is not int or v < 1 for v in asdict(self).values()):
            raise ValueError("Limits must be positive integers")


@dataclass(frozen=True)
class Result:
    t: int
    verdict: str
    possible: bool | None
    certain: bool | None
    reason: str | None
    metrics: dict


class Limited(RuntimeError):
    pass


def representatives(problem, t, compress=True):
    groups = defaultdict(list)
    for a in sorted(problem.universe):
        signature = tuple(a in problem.anchors[e] for e in problem.slots) + tuple(
            a in f.support for f in problem.fragments[:t])
        groups[signature].append(a)
    cap = max(len(problem.slots), problem.k + 1)
    selected = []
    for group in groups.values():
        selected.extend(group[:cap] if compress else group)
    return tuple(selected), len(groups)


class Query:
    def __init__(self, problem, t, scope, limits, compress, symmetry):
        self.problem, self.t, self.scope, self.limits = problem, t, scope, limits
        self.pool = IDPool()
        self.solver = Solver(name="g3")
        self.clauses = self.calls = self.refinements = self.blocks = 0
        self.stats = {"query_refinements": {}, "symmetry_enabled": False}
        self.assets, classes = representatives(problem, t, compress)
        self.stats.update(candidate_count=len(problem.universe), representative_count=len(self.assets),
                          candidate_classes=classes,
                          raw_association_upper_bound=prod(len(f.domain) for f in problem.fragments[:t]))
        self.x, self.occ, self.z = {}, {}, {}
        self.use_symmetry = symmetry

    def close(self):
        self.solver.delete()

    def var(self, key):
        v = self.pool.id(key)
        self.check_variables()
        return v

    def check_variables(self):
        if self.pool.top > self.limits.variables:
            raise Limited("variable_budget")

    def add(self, clause):
        self.check_variables()
        if self.clauses >= self.limits.clauses:
            raise Limited("clause_budget")
        self.solver.add_clause(clause)
        self.clauses += 1

    def cardinality(self, literals, bound, kind, guards=()):
        guards = list(guards)
        n = len(literals)
        if (kind == "atmost" and bound >= n) or (kind == "atleast" and bound <= 0):
            return
        if (kind == "atmost" and bound < 0) or (kind == "atleast" and bound > n):
            self.add(guards)
            return
        encoder = CardEnc.atmost if kind == "atmost" else CardEnc.atleast
        encoded = encoder(lits=literals, bound=bound, vpool=self.pool, encoding=EncType.seqcounter)
        self.check_variables()
        for clause in encoded.clauses:
            self.add([*guards, *clause])

    def build(self):
        p = self.problem
        fragments = p.fragments[:self.t]
        for i, f in enumerate(fragments):
            lits = []
            for e in p.slots:
                if e in f.domain:
                    v = self.var(("x", i, e))
                    self.x[i, e] = v
                    lits.append(v)
            self.add(lits)
            self.cardinality(lits, 1, "atmost")
        for e in p.slots:
            active = self.var(("active", e))
            self.occ[e] = active
            uses = [self.x[i, e] for i in range(self.t) if (i, e) in self.x]
            if self.scope == "known_targets":
                self.add([active])
            else:
                self.add([-active, *uses])
                for x in uses:
                    self.add([-x, active])
        for same, links in ((True, p.must_links), (False, p.cannot_links)):
            for i, j in links:
                if max(i, j) > self.t:
                    continue
                for e in p.slots:
                    left, right = self.x.get((i - 1, e)), self.x.get((j - 1, e))
                    if same:
                        if left and right:
                            self.add([-left, right])
                            self.add([-right, left])
                        elif left or right:
                            self.add([-(left or right)])
                    elif left and right:
                        self.add([-left, -right])
        symmetric = (len({p.anchors[e] for e in p.slots}) == 1
                     and all(f.domain == frozenset(p.slots) for f in fragments))
        if self.use_symmetry and symmetric:
            self.stats["symmetry_enabled"] = True
            for i in range(self.t):
                for j, e in enumerate(p.slots[1:], start=1):
                    self.add([-self.x[i, e], *[self.x[r, p.slots[j - 1]] for r in range(i)]])

        assignments = defaultdict(list)
        for e in p.slots:
            candidate_vars = {}
            identity_vars = []
            for a in self.assets:
                if a not in p.anchors[e]:
                    continue
                z = self.var(("candidate", e, a))
                candidate_vars[a] = z
                exclusions = [self.x[i, e] for i, f in enumerate(fragments)
                              if (i, e) in self.x and a not in f.support]
                for x in exclusions:
                    self.add([-z, -x])
                self.add([z, *exclusions])
                g = self.var(("identity", e, a))
                self.add([-g, self.occ[e]])
                self.add([-g, z])
                identity_vars.append(g)
                assignments[a].append(g)
            self.z[e] = candidate_vars
            self.add([-self.occ[e], *identity_vars])
            self.cardinality(identity_vars, 1, "atmost")
        for assignments_for_a in assignments.values():
            self.cardinality(assignments_for_a, 1, "atmost")

    def solve(self, *assumptions):
        self.calls += 1
        self.solver.conf_budget(self.limits.conflicts)
        result = self.solver.solve_limited(assumptions=list(assumptions))
        if result is None:
            raise Limited("solver_conflict_budget")
        return result

    def small_query(self, bound, label):
        selector = self.var(("query", label))
        choices = []
        for e in self.problem.slots:
            small = self.var(("small", label, e))
            choices.append(small)
            self.add([-small, self.occ[e]])
            self.cardinality(list(self.z[e].values()), bound, "atmost", [-small])
        self.add([-selector, *choices])
        return selector

    def nonrisk_query(self):
        selector = self.var(("query", "nonrisk"))
        for e in self.problem.slots:
            self.cardinality(list(self.z[e].values()), self.problem.k + 1, "atleast",
                             [-selector, -self.occ[e]])
        return selector

    def inspect(self, label):
        if self.refinements >= self.limits.refinements:
            raise Limited("refinement_budget")
        self.refinements += 1
        self.stats["query_refinements"][label] = self.stats["query_refinements"].get(label, 0) + 1
        positive = {v for v in self.solver.get_model() if v > 0}
        candidates, pattern = {}, []
        for e in self.problem.slots:
            active = self.occ[e] in positive
            pattern.append(self.occ[e] if active else -self.occ[e])
            if not active:
                continue
            candidates[e] = frozenset(a for a, z in self.z[e].items() if z in positive)
            pattern.extend(z if z in positive else -z for z in self.z[e].values())
        filtered = filter_alldifferent(candidates)
        if not filtered.feasible:
            raise AssertionError("SAT identity witness disagrees with matching")
        risk = any(1 <= len(c) <= self.problem.k for c in filtered.supported.values())
        return risk, pattern

    def search(self, selector, wanted, label):
        while self.solve(selector):
            risk, pattern = self.inspect(label)
            if risk == wanted:
                return True
            self.add([-selector, *[-literal for literal in pattern]])
            self.blocks += 1
        return False

    def verdict(self):
        self.build()
        if not self.solve():
            return "INCONSISTENT", False, False
        small = self.small_query(self.problem.k, "local_risk")
        if self.solve(small):
            risk, _ = self.inspect("local_risk")
            if not risk:
                raise AssertionError("feasible local risk must survive support filtering")
            possible = True
        elif len(self.problem.slots) <= self.problem.k + 1:
            possible = False
        else:
            relaxed = self.small_query(len(self.problem.slots) - 1, "potential_refined_risk")
            possible = self.search(relaxed, True, "potential_refined_risk")
        if not possible:
            return "SAFE", False, False
        nonrisk = self.search(self.nonrisk_query(), False, "nonrisk")
        return ("DEFER", True, False) if nonrisk else ("ALERT", True, True)

    def metrics(self):
        return {**self.stats, "variables": self.pool.top, "clauses": self.clauses,
                "solver_calls": self.calls, "refinements": self.refinements,
                "blocked_candidate_patterns": self.blocks}


def evaluate_prefix(problem: Problem, t: int, *, scope="occupied_targets", limits=None,
                    compress=True, symmetry=True):
    if type(t) is not int or not 0 <= t <= len(problem.fragments):
        raise ValueError("invalid prefix")
    if scope not in {"occupied_targets", "known_targets"}:
        raise ValueError("invalid scope")
    if type(compress) is not bool or type(symmetry) is not bool:
        raise ValueError("optimization switches must be boolean")
    started = perf_counter()
    query = Query(problem, t, scope, limits or Limits(), compress, symmetry)
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


def evaluate_stream(problem, *, on_prefix=None, **kwargs):
    prefixes = []
    first_p = first_c = None
    for t in range(len(problem.fragments) + 1):
        result = evaluate_prefix(problem, t, **kwargs)
        prefixes.append(result)
        if on_prefix:
            on_prefix(result)
        if result.verdict == "UNKNOWN":
            break
        if result.possible and first_p is None:
            first_p = t
        if result.certain and first_c is None:
            first_c = t
    complete = prefixes[-1].verdict != "UNKNOWN"
    return {"prefixes": prefixes, "complete": complete,
            "certified_through": prefixes[-1].t if complete else prefixes[-1].t - 1,
            "tau_possible": first_p, "tau_certain": first_c}
