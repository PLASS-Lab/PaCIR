"""Verify finite examples and recorded results."""

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def read(name):
    path = ROOT / name
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def tasks(name):
    with gzip.open(ROOT / "data" / (name + ".jsonl.gz"), "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def check(condition, label):
    if not condition:
        raise AssertionError(label)


def same(actual, expected, path="value"):
    if isinstance(expected, dict):
        check(isinstance(actual, dict), path)
        for key, value in expected.items():
            check(key in actual, path + "." + key)
            same(actual[key], value, path + "." + key)
    elif isinstance(expected, list):
        check(len(actual) == len(expected), path)
        for i, (a, b) in enumerate(zip(actual, expected)):
            same(a, b, path + "." + str(i))
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        check(isinstance(actual, (int, float)) and math.isclose(actual, expected, rel_tol=1e-8, abs_tol=1e-8), path)
    else:
        check(actual == expected, path)


def check_hashes():
    manifest = read("manifest.json")
    for relative, expected in manifest["files"].items():
        path = ROOT / relative
        check(path.resolve().is_relative_to(ROOT), "manifest path")
        check(hashlib.sha256(path.read_bytes()).hexdigest() == expected, "hash: " + relative)
    return len(manifest["files"])


def core():
    import finite_reference as f
    from engine import Limits
    from engine_exact_hall import evaluate_prefix
    from beam import Beam
    f.COUNTS.clear()
    f.exhaustive()
    u = frozenset("abc")
    triangle = tuple(map(frozenset, ("ab", "ac", "bc")))
    f.symbolic_check(u, triangle, (), 1, capacity=2)
    f.symbolic_check(u, triangle, (), 1)
    f.symbolic_check(u, tuple(map(frozenset, ("ab", "ab", "abc"))),
                     tuple((i, j, False) for i, j in itertools.combinations(range(3), 2)), 1)
    f.symbolic_check(u, triangle + (frozenset("ab"),), ((0, 3, False),), 1)
    expected = dict(static_inputs=9261, update_rebuild_checks=18522,
        supported_inclusion_checks=29168, conditional_truth_checks=53376,
        temporal_K_checks=55566, capacity_inclusion_checks=83349, symbolic_option_checks=664)
    same(dict(f.COUNTS), expected, "finite checks")
    budget_checks = []
    for bound, verdict in ((1, "UNKNOWN"), (2, "DEFER")):
        p = f.problem(u, tuple(map(frozenset, ("ab", "ac"))), (), 1)
        result = evaluate_prefix(p, 2, limits=Limits(refinements=bound))
        check(result.verdict == verdict and result.metrics["refinements"] == bound, "shared inspection budget")
        if verdict == "UNKNOWN":
            check(result.possible is None and result.certain is None, "UNKNOWN predicates")
        budget_checks.append(dict(limit=bound, verdict=verdict, inspections=result.metrics["refinements"]))
    for width in (1, 4, 16):
        b = Beam("abc", width=width)
        check(b.push("ab")["verdict"] == "SAFE", "baseline initial state")
        b.push("ac")
    return dict(**expected, inspection_budget=budget_checks, baseline_width_checks=3)


def recorded_references(inputs):
    recorded = read("data/callhome-reference-risks.json.gz")
    scope = read("data/design.json")["recorded_reference_only"]
    check(len(recorded) == scope["windows"], "recorded-only window count")
    check(not (inputs.keys() & recorded.keys()), "overlapping reference sources")
    prefixes = 0
    for window in recorded.values():
        check(set(window) == {"domain", "reference_risk"}, "recorded-only fields")
        check(window["domain"] == scope["domain"], "recorded-only domain")
        risk = window["reference_risk"]
        check(set(risk) == {"1", "3", "5"}, "recorded-only thresholds")
        lengths = {len(values) for values in risk.values()}
        check(len(lengths) == 1 and min(lengths) >= 3, "recorded-only risk length")
        check(all(type(v) is bool for values in risk.values() for v in values), "recorded-only risk type")
        check(all(not values[0] for values in risk.values()), "recorded-only initial risk")
        prefixes += len(risk["1"]) - 1
    check(prefixes == scope["cue_events_per_threshold"], "recorded-only prefix count")
    references = {ident: {key: window[key] for key in ("domain", "reference_risk")}
                  for ident, window in inputs.items()}
    references.update(recorded)
    return references, prefixes


def recorded_runs(references):
    import metrics
    output = {}
    for name in ("methods-k1", "methods-k35", "relations-k1", "relations-k35"):
        groups = defaultdict(list)
        stages = defaultdict(Counter)
        tail = defaultdict(Counter)
        seen = set()
        count = 0
        for task in tasks(name):
            count += 1
            ident = (task["id"], task["k"], task["condition"], task["method"])
            check(ident not in seen, "duplicate task")
            seen.add(ident)
            n = task["n"]
            source = references[task["id"]]
            check(source["domain"] == task["domain"], "reference domain")
            reference = source["reference_risk"][str(task["k"])]
            check(len(reference) == n + 1, "reference denominator")
            check(len(task["records"]) == n + (2 if task["condition"] == "all-delayed-2" else 0), "event denominator")
            for t, row in enumerate(task["records"], 1):
                check((row["event_time"], row["clues"], row["observation"]) == (t, min(n, t), t <= n), "event clock")
                if task["method"] != "exact":
                    continue
                if row["verdict"] in ("SAFE", "DEFER", "ALERT"):
                    pair = {"SAFE": (False, False), "DEFER": (True, False), "ALERT": (True, True)}[row["verdict"]]
                    check((row.get("possible"), row.get("certain")) == pair, "risk predicates")
                if t > n:
                    tail[(task["k"], task["condition"])][row["verdict"]] += 1
                    continue
                if row["verdict"] not in ("SAFE", "DEFER", "ALERT"):
                    continue
                sm = row.get("solver_metrics", {})
                q = sm.get("query_refinements", {})
                c = stages[(task["k"], task["condition"])]
                if q.get("local_risk", 0):
                    c["direct_sat"] += 1
                elif q.get("potential_refined_risk", 0):
                    c["hall_sat"] += 1
                    c["hall_sat_" + row["verdict"]] += 1
                    c["hall_sat_reference_risk"] += reference[t]
                elif row["verdict"] == "SAFE":
                    c["safe_calls_" + str(sm.get("solver_calls"))] += 1
                if q.get("nonrisk", 0):
                    c["nonrisk_inspected_" + row["verdict"]] += 1
                if q.get("nonrisk", 0) > 1:
                    c["nonrisk_multiple_" + row["verdict"]] += 1
            policies = metrics.policy_labels(task)
            compact = {k: task[k] for k in ("complete", "resource_measurement_missing", "wall_seconds", "peak_rss_bytes")}
            compact["records"] = [{k: r[k] for k in ("observation", "verdict", "seconds", "top_score_tied") if k in r} for r in task["records"]]
            compact["scores"] = {policy: metrics.score_labels(labels, reference, n) for policy, labels in policies.items()}
            for policy in policies:
                for domain in (task["domain"], "ALL"):
                    groups[(domain, task["k"], task["condition"], policy)].append((compact, policy))
        table = []
        for (domain, k, condition, policy), entries in sorted(groups.items()):
            table.append(dict(domain=domain, k=k, condition=condition, policy=policy, **metrics.aggregate(entries)))
        output[name] = dict(tasks=count, table=table,
            stages={f"{k}:{condition}": dict(c) for (k, condition), c in stages.items()},
            tail={f"{k}:{condition}": dict(c) for (k, condition), c in tail.items()})
        print(name + ": " + str(count) + " tasks", flush=True)
    return output


def quantile(values, probability):
    values = sorted(values)
    return values[max(0, math.ceil(probability * len(values))-1)] if values else None


def distribution(values):
    return dict(n=len(values), median=quantile(values, .5), p95=quantile(values, .95), maximum=max(values) if values else None, total=sum(values))


def input_references(inputs):
    from reference_capacity import project
    scope = read("data/design.json")["public_inputs"]
    check(len(inputs) == scope["windows"], "public input window count")
    check(dict(Counter(w["domain"] for w in inputs.values())) == scope["domains"], "public input domains")
    checked = 0
    for window in inputs.values():
        domains = {}
        check(len(window["supports"]) == len(window["reference_partition"]), "input partition length")
        for t, (support, label) in enumerate(zip(window["supports"], window["reference_partition"]), 1):
            check(support and len(set(support)) == len(support), "candidate set")
            check(all(type(a) is int and 0 <= a < window["candidate_count"] for a in support), "candidate index")
            domains[label] = domains[label] & set(support) if label in domains else set(support)
            refined = project(tuple(domains.values()))
            check(refined is not None, "reference assignment feasibility")
            for k in (1, 3, 5):
                expected = any(1 <= len(s) <= k for s in refined)
                check(window["reference_risk"][str(k)][t] == expected, "independent reference risk")
            checked += 1
        for packet in window["packets"]:
            i, j = packet["left"], packet["right"]
            check(1 <= j < i == packet["created"] <= len(window["supports"]), "relation causality")
            check((window["reference_partition"][i-1] == window["reference_partition"][j-1]) == (packet["kind"] == "same"), "reference relation")
    check(checked == scope["cue_events_per_threshold"], "reference prefix count")
    return checked


def ablations():
    output = {}
    original_k35 = set()
    for name in ("ablation-initial", "ablation-sequential", "ablation-hall", "ablation-synthetic", "ablation-k35", "ablation-remeasurement"):
        by = defaultdict(dict)
        for task in tasks(name):
            by[(task["variant"], task["k"])][task["id"]] = task
        result = {f"{variant}:{k}": dict(tasks=len(items), completed=sum(t["complete"] for t in items.values()),
                     stop_reasons=dict(Counter(t["stop_reason"] for t in items.values() if not t["complete"])))
                  for (variant, k), items in sorted(by.items())}
        if name == "ablation-k35":
            original_k35 = {(w, k, variant) for (variant, k), items in by.items() for w in items}
        if name == "ablation-remeasurement":
            jobs = read("data/selection.json.gz")["remeasurement_jobs"]
            selected = {(j["id"], j["k"], j["variant"]) for j in jobs}
            observed = {(w, k, variant) for (variant, k), items in by.items() for w in items}
            check(len(selected) == len(jobs) and selected == observed and selected <= original_k35, "remeasurement selection")
            result["selection"] = dict(Counter(j["role"] for j in jobs))
        if name in ("ablation-hall", "ablation-synthetic"):
            ref = by[("exact-gen", 1)]
            selected = {w for w, t in ref.items() if t.get("group") != "control"}
            relaxed = {(w, r["event_time"]) for w in selected for r in ref[w]["records"] if "projection_risk_search" in r["solver_metrics"]}
            def status(r):
                if r.get("attempted"):
                    return "completed" if r["verdict"] != "UNKNOWN" else "limit" if r.get("reason") == "refinement_budget" else "other-unknown"
                return "wall" if r.get("reason") in ("wall_limit", "memory_limit") else "not-attempted"
            tables = {}
            for (variant, k), items in sorted(by.items()):
                states, inspections = Counter(), []
                for w, event in relaxed:
                    r = items[w]["records"][event-1]
                    s = status(r)
                    states[s] += 1
                    if s == "completed":
                        inspections.append(r["solver_metrics"].get("query_refinements", {}).get("potential_refined_risk", 0))
                tables[variant] = dict(status=dict(states), risk_inspections=distribution(inspections))
            pairs = []
            for w in selected:
                a, b = by[("exact-insp", 1)][w], ref[w]
                for ra, rb in zip(a["records"], b["records"]):
                    qa, qb = (r["solver_metrics"].get("query_refinements", {}).get("nonrisk", 0) for r in (ra, rb))
                    if ((status(ra) == "completed" and qa > 1) or (status(rb) == "completed" and qb > 1)) and status(ra) == status(rb) == "completed":
                        pairs.append((qa, qb))
            result["hall"] = dict(relaxed_events=len(relaxed), variants=tables,
                nonrisk_pairs=len(pairs), nonrisk_inspected_only=sum(a for a, b in pairs), nonrisk_generalized=sum(b for a, b in pairs))
        if name == "ablation-sequential":
            ratios = {}
            full = by[("full", 1)]
            for variant in ("no-reduction", "no-symmetry"):
                groups = defaultdict(list)
                for w, task in by[(variant, 1)].items():
                    if task["complete"] and full[w]["complete"]:
                        a = sum(r["seconds"] or 0 for r in task["records"] if r.get("attempted"))
                        b = sum(r["seconds"] or 0 for r in full[w]["records"] if r.get("attempted"))
                        if b:
                            groups[task["domain"]].append(a/b)
                ratios[variant] = {d: distribution(v) for d, v in groups.items()}
            result["paired_compute_ratios"] = ratios
        output[name] = result
        print(name + ": " + str(sum(len(v) for v in by.values())) + " tasks", flush=True)
    return output


def irc():
    import irc_metrics as m
    data = read("data/irc.json.gz")
    risk = {(t["window"], t["k"], t["method"]): t for t in data["risks"]}
    rows, onset_rows = [], []
    fixed_checks = 0
    for window in data["windows"]:
        cache = {}
        for t in range(1, len(window["supports"])+1):
            gold, cause = m.fixed_partition(window["supports"][:t], window["reference"][:t])
            check(cause is None, "IRC reference feasibility")
            owners = window["predicted"][:t]
            if None in owners:
                predicted, cause = None, "missing_linkage"
            else:
                predicted, cause = m.fixed_partition(window["supports"][:t], owners)
                fixed_checks += 1
            cache[t] = (gold, predicted, cause)
        for k in (1, 3, 5):
            current = []
            for t, (gold, predicted, cause) in cache.items():
                pr = risk[(window["id"], k, "pacir")]["records"][t-1]
                dr = risk[(window["id"], k, "dla")]["records"][t-1]
                dv = "NOT_EVALUATED" if cause == "missing_linkage" else "INVALID_PARTITION" if predicted is None else "ALERT" if any(x <= k for x in predicted) else "SAFE"
                check(dr["verdict"] == dv and dr["sizes"] == (predicted or []), "IRC fixed-partition risk")
                item = dict(window=window["id"], source=window["file"], k=k, t=t,
                    truth=any(x <= k for x in gold), dla=dv, pacir=pr["verdict"])
                check(not (item["pacir"] == "SAFE" and item["truth"] or item["pacir"] == "ALERT" and not item["truth"]), "IRC reference risk agreement")
                current.append(item)
                rows.append(item)
            onset_rows.append(dict(k=k, **{method: m.onset(current, method) for method in ("dla", "pacir")}))
    tables = {}
    for k in (1, 3, 5):
        subset = [r for r in rows if r["k"] == k]
        valid = [r for r in subset if r["dla"] in ("SAFE", "ALERT")]
        tables[str(k)] = dict(full={method: m.rates(subset, method) for method in ("dla", "pacir")},
            common={method: m.rates(valid, method) for method in ("dla", "pacir")},
            onset={method: dict(Counter(r[method]["category"] for r in onset_rows if r["k"] == k)) for method in ("dla", "pacir")})
    clustering = []
    statuses = Counter()
    for file in data["files"]:
        statuses.update(r["status"] for r in file["messages"])
        available = [r for r in file["messages"] if r["predicted"] is not None]
        users = [r for r in available if r["is_user"]]
        clustering.append(dict(file=file["id"], all_messages=m.clustering([r["reference"] for r in available], [r["predicted"] for r in available])[0],
            user_only=m.clustering([r["reference"] for r in users], [r["predicted"] for r in users])[0]))
    calls = data["calls"]
    cost = dict(calls=len(calls), input_tokens=sum(r["input_tokens"] for r in calls), output_tokens=sum(r["output_tokens"] for r in calls),
        request_wall_seconds=sum(r["wall_seconds"] for r in calls), inherited_calls=sum(r["inherited"] for r in calls),
        retry_calls=sum(r["attempt"] > 1 for r in calls), failed_first_calls=sum(r["attempt"] == 1 and not r["valid"] for r in calls))
    for method in ("dla", "pacir"):
        cost[method + "_risk_wall_seconds"] = sum(t["wall_seconds"] for t in data["risks"] if t["method"] == method)
    return dict(tables=tables, clustering=clustering, message_statuses=dict(statuses), cost=cost, independently_checked_available_partitions=fixed_checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-only", action="store_true")
    parser.add_argument("--records-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True, help="New output JSON outside this package")
    args = parser.parse_args()
    output = args.output.resolve()
    check(not output.is_relative_to(ROOT), "Output must be outside the package")
    check(not output.exists(), "Output already exists")
    result = dict(verified_files=check_hashes())
    if not args.records_only:
        result["finite_verification"] = core()
        print("Finite verification passed", flush=True)
    if not args.core_only:
        inputs = read("data/inputs.json.gz")
        result["independent_reference_prefixes"] = input_references(inputs)
        print("Independent reference risks: " + str(result["independent_reference_prefixes"]) + " prefixes", flush=True)
        references, recorded_prefixes = recorded_references(inputs)
        result["recorded_reference_only_prefixes"] = recorded_prefixes
        design = read("data/design.json")
        check(len(references) == design["windows"], "full reference window count")
        check(result["independent_reference_prefixes"] + recorded_prefixes == design["cue_events_per_threshold"], "full reference prefix count")
        print("Recorded-only CallHome reference risks: " + str(recorded_prefixes) + " prefixes", flush=True)
        result["runs"] = recorded_runs(references)
        result["ablations"] = ablations()
        result["irc"] = irc()
        expected = read("expected.json")
        for entry in expected:
            actual = result
            for component in entry["path"]:
                actual = actual[component]
            same(actual, entry["value"], ".".join(map(str, entry["path"])))
        result["checked_reference_entries"] = len(expected)
    result["status"] = "PASS"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PASS: " + str(output), flush=True)


if __name__ == "__main__":
    main()
