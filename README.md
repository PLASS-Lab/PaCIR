# PaCIR

**Possible and Certain Candidate-Based Identification Risk under Uncertain Subject Linkage**

Yeongseop Lee, ChanSung Jung, and Yunsik Son

PaCIR evaluates possible and certain candidate-count risk across admissible cue-to-subject linkage hypotheses. This repository contains the solver, structured evaluation inputs, recorded results, and verification code accompanying the manuscript.

## Run

Use Python 3.12. Dependencies are pinned in `requirements.txt`; the SAT backend is Glucose 3.

From the repository root:

```sh
python -m pip install -r requirements.txt
python -B code/verify.py --output ../verification-results.json
```

A successful run prints `PASS` and writes the verification results as JSON.
Use `--core-only` for finite checks or `--records-only` for recorded results.

## Contents

| Path | Contents |
| --- | --- |
| `code/engine*.py`, `code/monitor.py`, `code/identity_filter.py` | Symbolic solver, candidate reduction, and matching |
| `code/beam.py` | Score-based linkage baselines |
| `code/finite_reference.py`, `code/reference_capacity.py` | Independent reference calculations |
| `code/metrics.py`, `code/irc_metrics.py`, `code/verify.py` | Evaluation metrics and verification |
| `data/inputs.json.gz` | Candidate sets, reference partitions and risks, and relation packets for 2,234 windows from Switchboard, Ubuntu IRC, TAB, and ATT&CK |
| `data/callhome-reference-risks.json.gz` | Recorded reference risk labels for 64 CallHome windows; candidate sets, partitions, and relation packets are excluded |
| `data/methods-*.jsonl.gz`, `data/relations-*.jsonl.gz` | Method comparisons and relation-condition results at K = 1, 3, 5 |
| `data/ablation-*.jsonl.gz` | Component, Hall-query, synthetic, and remeasurement results |
| `data/irc.json.gz` | IRC inputs, partitions, risk outputs, and model-call costs |
| `data/design.json`, `data/selection.json.gz` | Experimental settings and remeasurement selection |
| `expected.json` | Reference aggregates |
| `manifest.json` | SHA-256 checksums for code, data, dependencies, and reference aggregates |

## Verification

The verifier checks 9,261 finite reference inputs, 664 symbolic comparisons, two inspection-budget cases, and independent reference risk at 45,294 cue prefixes from the four included input domains. CallHome's 260 prefixes use recorded reference risk labels for aggregation, without recomputing them from inputs. Across all five domains, it recalculates decision rates, onsets, decision paths, ablation statistics, IRC linkage metrics, and cost aggregates and checks 312 reference entries. Timing measurements are read from the records.

Dataset construction and experimental protocols are described in the manuscript and Supplementary Sections S1-S7.

## Data Format

- Data files use UTF-8 and gzip. Each `.jsonl.gz` line is one task; each `.json.gz` file contains one JSON object.
- Window IDs link records across runs. Candidate IDs are window-local integers in original lexical order; partition labels identify blocks. IRC files `f01`-`f10` follow the supplementary linkage-quality table, with positions relative to each 500-message slice.
- Events are one-based; `reference_risk[k][0]` is the initial state. Main rates use cue-adding events (`observation = true`); delayed post-window events are counted separately.
- `DEFER` denotes risk ambiguity; `ABSTAIN` denotes baseline abstention. `UNKNOWN` with `attempted = true` denotes interrupted computation; `attempted = false` and `NOT_EVALUATED` identify unevaluated records.
- `seconds` and `wall_seconds` use seconds; `peak_rss_bytes` uses bytes. Consensus and margin policies share worker measurements. IRC call costs are counted once across thresholds, including retries.
- Component slowdown ratios use jointly completed sequential reruns. Hall exclusion ratios use common events; inspection totals use completed events selected by the exact query. Replacement records supersede selected original tasks; bridge records serve diagnostics.
- IRC rates distinguish all 903 prefixes from the 484-prefix feasible-prediction subset. Missing and infeasible predictions contribute no decisions or errors.

## Sources

The evaluations use [ISIP MS98 Switchboard](https://isip.piconepress.com/projects/switchboard/), [CABank English CallHome](https://doi.org/10.21415/T5KP54), [annotated Ubuntu IRC](https://doi.org/10.18653/v1/P19-1374), [TAB](https://doi.org/10.1162/coli_a_00458), and [MITRE Enterprise ATT&CK v19.2](https://github.com/mitre/cti/tree/8543c5b05bd9bbcace9fc37f30bba96b675b6f33/enterprise-attack). CABank-derived input structures are not included in this repository.

Repository citation metadata is provided in [CITATION.cff](CITATION.cff).

## Licenses

PaCIR code is licensed under [MIT](LICENSE). Author-created documentation and experimental results are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Source-specific terms for processed inputs and attribution notices are listed in [DATA_LICENSES.md](DATA_LICENSES.md).
