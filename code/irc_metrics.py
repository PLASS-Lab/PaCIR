"""Independent fixed-partition support, risk, clustering, and onset calculations."""

from collections import Counter
import math
def sat_matching(domains):
    # Augmenting paths on a fixed bipartite graph, independent of Regin/SAT code.
    matched = {}

    def visit(i, seen):
        for value in sorted(domains[i]):
            if value in seen:
                continue
            seen.add(value)
            if value not in matched or visit(matched[value], seen):
                matched[value] = i
                return True
        return False

    return all(visit(i, set()) for i in sorted(range(len(domains)), key=lambda i: len(domains[i])))



def supported(domains):
    if not sat_matching(domains):
        return None
    result = []
    for i, domain in enumerate(domains):
        keep = set()
        for value in domain:
            rest = [d - {value} for j, d in enumerate(domains) if j != i]
            if sat_matching(rest):
                keep.add(value)
        result.append(keep)
    return result



def fixed_partition(supports, owners):
    groups = {}
    for domain, owner in zip(supports, owners):
        groups[owner] = groups[owner] & set(domain) if owner in groups else set(domain)
    ds = list(groups.values())
    result = supported(ds)
    if result is None:
        return None, "empty_intersection" if any(not d for d in ds) else "no_injective_assignment"
    return sorted(map(len, result)), None



def rates(rows, method):
    n = len(rows)
    risk = sum(r["truth"] for r in rows)
    nonrisk = n - risk
    fs = sum(r[method] == "SAFE" and r["truth"] for r in rows)
    fa = sum(r[method] == "ALERT" and not r["truth"] for r in rows)
    decided = sum(r[method] in ("SAFE", "ALERT") for r in rows)
    return dict(n=n, truth_risk=risk, truth_nonrisk=nonrisk, false_safe=fs, false_alarm=fa,
                FSR=fs / risk if risk else None, FAR=fa / nonrisk if nonrisk else None,
                decision_rate=decided / n if n else None,
                verdicts=dict(Counter(r[method] for r in rows)))



def onset(rows, method):
    truth = next((r["t"] for r in rows if r["truth"]), None)
    found = next((r["t"] for r in rows if r[method] == "ALERT"), None)
    unresolved = [r["t"] for r in rows if r[method] not in ("SAFE", "ALERT", "DEFER")]
    if unresolved and (found is None or min(unresolved) < found):
        category = "unresolved_before_first_observed_alert"
    elif found is None:
        category = "no_alert_within_window"
    elif truth is None or found < truth:
        category = "early"
    elif found == truth:
        category = "same_event"
    else:
        category = "delayed"
    return dict(truth_first_risk=truth, first_observed_alert=found, category=category,
                unresolved_events=unresolved,
                scope="within fixed 60-user-message risk window; model alert is not a certified onset")



def clustering(gold, pred):
    n = len(gold)
    gc, pc, joint = Counter(gold), Counter(pred), Counter(zip(gold, pred))
    choose = lambda c: c * (c - 1) / 2
    gp, pp, tp = (sum(map(choose, c.values())) for c in (gc, pc, joint))
    expected = gp * pp / choose(n) if n > 1 else 0
    ari = (tp - expected) / ((gp + pp) / 2 - expected) if (gp + pp) / 2 != expected else 1.0
    hg = -sum(c / n * math.log2(c / n) for c in gc.values()) if n else 0
    hp = -sum(c / n * math.log2(c / n) for c in pc.values()) if n else 0
    mi = sum(c / n * math.log2(c * n / (gc[g] * pc[p])) for (g, p), c in joint.items()) if n else 0
    exact = sum(1 for (g, p), c in joint.items() if c == gc[g] == pc[p])
    saved = dict(n=n, ARI=ari if n else None, VI_bits=max(0, hg + hp - 2 * mi),
                 exact_cluster_precision=exact / len(pc) if pc else None,
                 exact_cluster_recall=exact / len(gc) if gc else None,
                 exact_cluster_F1=2 * exact / (len(gc) + len(pc)) if n else None)
    pair = dict(gold_pairs=gp, predicted_pairs=pp, correct_pairs=tp,
                precision=tp / pp if pp else None, recall=tp / gp if gp else None)
    return saved, pair

