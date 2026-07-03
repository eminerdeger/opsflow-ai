# Incident Report

- **Generated:** 2026-07-03T03:29:20+00:00
- **Events source:** `sample_data/events.jsonl`
- **Anomalies source:** `sample_data/anomalies.json`
- **Anomalies diagnosed:** 1

> All data in this report is synthetic. Diagnosis is produced by a deterministic, rule-based RCA workflow that inspects computed evidence — it is not an LLM.

## ANOM_0001 — failure_rate_spike (high)

### Incident summary

Between **2026-07-03T02:35:00+00:00** and **2026-07-03T03:05:00+00:00**, the failure rate rose to **47.7%** against a baseline of **2.7%** (123 failures across 258 events). Failures concentrated on **OCR_GATE_02** at **LOC_A02**.

### Anomaly details

- Detection type: failure_rate_spike, peak robust z-score 8.62
- Window: 2026-07-03T02:35:00+00:00 → 2026-07-03T03:05:00+00:00
- Severity: high

### Timeline

- First failure in window: 2026-07-03T02:35:21.163328+00:00
- Peak bucket: 2026-07-03T02:45:00+00:00 (27 failures, 56.2% failure rate)
- Last failure in window: 2026-07-03T03:04:52.700692+00:00

| Bucket start | Events | Failures | Failure rate |
|---|---:|---:|---:|
| 2026-07-03T02:35:00+00:00 | 46 | 17 | 37.0% |
| 2026-07-03T02:40:00+00:00 | 38 | 17 | 44.7% |
| 2026-07-03T02:45:00+00:00 | 48 | 27 | 56.2% |
| 2026-07-03T02:50:00+00:00 | 42 | 21 | 50.0% |
| 2026-07-03T02:55:00+00:00 | 47 | 26 | 55.3% |
| 2026-07-03T03:00:00+00:00 | 37 | 15 | 40.5% |

### Baseline vs anomaly comparison

| Metric | Baseline | Anomaly window | Delta |
|---|---:|---:|---:|
| Failure rate | 2.7% | 47.7% | +45.0% |
| Avg confidence_score | 0.908 | 0.475 | -0.433 |
| Avg retry_count | 0.09 | 1.90 | +1.81 |

### Affected component / location (blast radius)

- Affected components: OCR_GATE_02, SORTER_01
- Affected locations: LOC_A02
- Correlation IDs impacted: 104 of 192 in window (54.2%)
- Window traffic share of total stream: 25.8%

### Evidence

**Failure concentration (share of failed events):**

- Component OCR_GATE_02: 122 failures (99%)
- Component SORTER_01: 1 failures (1%)
- Location LOC_A02: 123 failures (100%)

**Error code concentration:**

- ERR_OCR_LOW_CONFIDENCE: 80 (65%)
- ERR_OCR_TIMEOUT: 41 (33%)
- ERR_TRACKING_LOST: 1 (1%)

**Retry/confidence correlation:** r=-0.784 over 175 events — strong negative correlation: retries track low confidence

**Tool invocations (diagnostic trace):**

- `filter_events_by_window` → 258 of 1000 events fall inside the anomaly window
- `compare_baseline_vs_anomaly` → failure rate 2.7% → 47.7%
- `find_component_concentration` → top: OCR_GATE_02 (99% of failures)
- `find_location_concentration` → top: LOC_A02 (100% of failures)
- `find_error_code_concentration` → top: ERR_OCR_LOW_CONFIDENCE (65%)
- `correlate_retry_count_and_confidence` → r=-0.784 (strong negative correlation: retries track low confidence)
- `build_timeline` → 6 buckets; first failure 2026-07-03T02:35:21.163328+00:00
- `estimate_blast_radius` → 123 failures across 2 component(s), 104 correlation id(s) affected
- `generate_hypothesis` → confidence=high (evidence score 7)
- `generate_recommended_actions` → 5 actions

### Root-cause hypothesis

Localized read-quality degradation on OCR_GATE_02 at LOC_A02: confidence collapsed while retries and failures spiked on this component only (dominant error: ERR_OCR_LOW_CONFIDENCE). Most consistent with a physical/optical or component-level fault (e.g. dirty or misaligned camera, lighting change, or degraded sensor) rather than an upstream/systemic failure.

**Confidence level:** high (evidence score 7/7)

Reasoning:

- 99% of failures concentrate on a single component (OCR_GATE_02), indicating a localized fault rather than a systemic outage.
- Average confidence_score dropped by 0.43 vs baseline, consistent with degraded read quality.
- Average retry_count rose by 1.81 vs baseline.
- Retry count and confidence are strongly negatively correlated (r=-0.784), so retries are driven by low-quality reads.
- A single error code (ERR_OCR_LOW_CONFIDENCE) accounts for 65% of coded errors in the window.

### Recommended actions

1. Inspect OCR_GATE_02 at LOC_A02: check physical condition, alignment, lens/sensor cleanliness, and lighting.
2. Review component logs and recent configuration or firmware changes for OCR_GATE_02 around the anomaly window start.
3. Correlate the dominant error code (ERR_OCR_LOW_CONFIDENCE) with the component vendor's runbook / known failure modes.
4. Temporarily route traffic away from the affected component (or enable the fallback/manual handling path) until read quality recovers.
5. Monitor confidence_score and retry_count on the affected component after intervention to confirm recovery against the baseline.

## Limitations / Assumptions

- All events are synthetically generated; scenarios approximate real operational failure modes but are simplifications.
- The RCA workflow is deterministic and rule-based: it localizes faults from statistical evidence (concentration, deltas, correlation) and maps them to known failure-mode templates. It cannot discover novel causes.
- Detection uses per-bucket failure rates with robust statistics; short spikes below one bucket width or gradual degradations may be missed.
- Baseline is derived from the non-anomalous part of the same stream; a fully degraded stream would weaken the comparison.
