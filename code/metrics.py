"""Recorded verdict, abstention, onset, and cost metrics."""

from collections import Counter
from fractions import Fraction
import math
import statistics
VALID = ("SAFE", "DEFER", "ALERT", "INCONSISTENT")
TERMINAL = ("UNKNOWN", "ERROR", "BRANCH_FAILURE")
THRESHOLDS = ("0", "0.05", "0.10", "0.20", "0.40", "0.80", "1.00")

def require(condition, message):
    if not condition:
        raise AssertionError(message)

def policy_labels(task):
    method = task['method']
    base = [r['verdict'] for r in task['records']]
    policies = {method: base}
    if method in ('pair-beam4', 'pair-beam16'):
        policies[method+'-retained-consensus'] = [r['consensus'] if r['verdict'] in VALID else r['verdict'] for r in task['records']]
    if method == 'pair-greedy':
        for threshold in THRESHOLDS:
            policies['pair-greedy-reject@'+threshold] = [
                'ABSTAIN' if r['verdict'] in ('SAFE', 'ALERT') and Fraction(r['margin']) < Fraction(threshold) else r['verdict']
                for r in task['records']]
    return policies



def score_labels(labels, truth, n):
    require(len(truth) == n+1 and truth[0] is False, 'bad truth clock')
    counts, risk_counts, safe_counts = Counter(), Counter(), Counter()
    for t, label in enumerate(labels[:n], 1):
        counts[label] += 1
        (risk_counts if truth[t] else safe_counts)[label] += 1
    first_truth = next((t for t in range(1, n+1) if truth[t]), None)
    first = next((t for t, label in enumerate(labels[:n], 1) if label == 'ALERT'), None)
    tail = next((t for t, label in enumerate(labels, 1) if label == 'ALERT'), None)
    failures = [t for t, label in enumerate(labels[:n], 1) if label in (*TERMINAL, 'NOT_EVALUATED')]
    timing = 'nonrisk' if first_truth is None else (
        'early' if first < first_truth else 'on_time' if first == first_truth else 'late') if first is not None else (
        'unevaluated_termination' if failures else 'no_alert_complete')
    decided = counts['SAFE'] + counts['ALERT']
    return dict(counts=dict(counts), risk_counts=dict(risk_counts), nonrisk_counts=dict(safe_counts),
                false_safe=risk_counts['SAFE'], false_alert=safe_counts['ALERT'],
                decision_n=decided, first_truth=first_truth, tau_alert_pred=first,
                first_alert_including_tail=tail, timing=timing,
                delay_if_late=first-first_truth if timing == 'late' else None,
                no_alert_followup=n-first_truth if timing == 'no_alert_complete' else None,
                first_failure=failures[0] if failures else None,
                end_of_window=labels[n-1], end_after_tail=labels[-1])



def describe(values):
    if not values:
        return dict(n=0, mean=None, median=None, p95=None, maximum=None)
    values = sorted(values)
    return dict(n=len(values), mean=statistics.mean(values), median=statistics.median(values),
                p95=values[math.ceil(.95*len(values))-1], maximum=values[-1])



def aggregate(entries):
    counts, risky, nonrisk, timings = (Counter() for _ in range(4))
    delay, followup, wall, events = ([] for _ in range(4))
    complete, risk_windows, alerted, tied, tie_den = 0, 0, 0, 0, 0
    for task, policy in entries:
        s = task['scores'][policy]
        counts.update(s['counts']); risky.update(s['risk_counts']); nonrisk.update(s['nonrisk_counts'])
        timings[s['timing']] += 1
        complete += task['complete']
        risk_windows += s['first_truth'] is not None
        alerted += s['first_truth'] is not None and s['tau_alert_pred'] is not None
        if s['delay_if_late'] is not None:
            delay.append(s['delay_if_late'])
        if s['no_alert_followup'] is not None:
            followup.append(s['no_alert_followup'])
        if not task['resource_measurement_missing']:
            wall.append(task['wall_seconds'])
        for r in task['records']:
            if r['observation'] and r['verdict'] in VALID:
                events.append(r['seconds'])
                if 'top_score_tied' in r:
                    tie_den += 1
                    tied += r['top_score_tied']
    total, decisions = sum(counts.values()), counts['SAFE']+counts['ALERT']
    pct = lambda a,b: 100*a/b if b else None
    return dict(windows=len(entries), complete_windows=complete, observation_prefixes=total,
                verdict_counts=dict(counts), risk_counts=dict(risky), nonrisk_counts=dict(nonrisk),
                decision_pct=pct(decisions,total), false_safe=risky['SAFE'], false_alert=nonrisk['ALERT'],
                false_safe_pct=pct(risky['SAFE'],sum(risky.values())), false_alert_pct=pct(nonrisk['ALERT'],sum(nonrisk.values())),
                selective_error_pct=pct(risky['SAFE']+nonrisk['ALERT'],decisions), timing=dict(timings),
                risk_windows=risk_windows, risk_windows_alerted=alerted, risk_window_alert_pct=pct(alerted,risk_windows),
                late_delay=describe(delay), no_alert_followup=describe(followup),
                worker_wall_seconds=describe(wall), observation_event_seconds=describe(events),
                peak_observed_rss_MiB=max(t['peak_rss_bytes'] for t,p in entries)/1048576,
                resource_measurement_missing_windows=sum(t['resource_measurement_missing'] for t,p in entries),
                top_score_tied_events=tied, top_score_tie_denominator=tie_den,
                resource_note='shared worker cost for derived reject/consensus policies; do not sum rows')

