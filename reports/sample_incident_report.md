# Incident Report

- **Generated:** 2026-07-03T17:00:52+00:00
- **Events source:** `sample_data/events.jsonl`
- **Anomalies source:** `sample_data/anomalies.json`
- **Anomalies diagnosed:** 1

> All data in this report is synthetic. Diagnosis is produced by a deterministic, rule-based RCA workflow that inspects computed evidence — it is not an LLM.

## ANOM_0001 — failure_rate_spike (high)

### Incident summary

Between **2026-07-03T16:05:00+00:00** and **2026-07-03T16:40:00+00:00**, the failure rate rose to **41.2%** against a baseline of **2.5%** (126 failures across 306 events). Failures concentrated on **OCR_GATE_02** at **LOC_A02**.

### Anomaly details

- Detection type: failure_rate_spike, peak robust z-score 12.48
- Window: 2026-07-03T16:05:00+00:00 → 2026-07-03T16:40:00+00:00
- Severity: high

### Timeline

- First failure in window: 2026-07-03T16:06:53.500648+00:00
- Peak bucket: 2026-07-03T16:20:00+00:00 (26 failures, 59.1% failure rate)
- Last failure in window: 2026-07-03T16:39:11.773518+00:00

| Bucket start | Events | Failures | Failure rate |
|---|---:|---:|---:|
| 2026-07-03T16:05:00+00:00 | 51 | 11 | 21.6% |
| 2026-07-03T16:10:00+00:00 | 39 | 19 | 48.7% |
| 2026-07-03T16:15:00+00:00 | 51 | 23 | 45.1% |
| 2026-07-03T16:20:00+00:00 | 44 | 26 | 59.1% |
| 2026-07-03T16:25:00+00:00 | 39 | 20 | 51.3% |
| 2026-07-03T16:30:00+00:00 | 42 | 18 | 42.9% |
| 2026-07-03T16:35:00+00:00 | 40 | 9 | 22.5% |

### Baseline vs anomaly comparison

| Metric | Baseline | Anomaly window | Delta |
|---|---:|---:|---:|
| Failure rate | 2.5% | 41.2% | +38.7% |
| Avg confidence_score | 0.914 | 0.513 | -0.401 |
| Avg retry_count | 0.09 | 1.62 | +1.54 |
| Avg duration_ms | 298 | 507 | +209 |

### Affected component / location (blast radius)

- Affected components: OCR_GATE_01, OCR_GATE_02, SORTER_01
- Affected locations: LOC_A02
- Correlation IDs impacted: 107 of 231 in window (46.3%)
- Window traffic share of total stream: 30.6%

### Evidence

**Failure concentration (share of failed events):**

- Component OCR_GATE_02: 124 failures (98%)
- Component SORTER_01: 1 failures (1%)
- Component OCR_GATE_01: 1 failures (1%)
- Location LOC_A02: 126 failures (100%)
- Event type ocr_read: 125 failures (99%)
- Event type processing_delay: 1 failures (1%)

**Error code concentration:**

- ERR_OCR_LOW_CONFIDENCE: 82 (65%)
- ERR_OCR_TIMEOUT: 41 (33%)
- ERR_TRACKING_LOST: 1 (1%)

**Retry/confidence correlation:** r=-0.817 over 195 events — strong negative correlation: retries track low confidence

**Tool invocations (diagnostic trace):**

- `filter_events_by_window` → 306 of 1000 events fall inside the anomaly window
- `compare_baseline_vs_anomaly` → failure rate 2.5% → 41.2%
- `find_component_concentration` → top: OCR_GATE_02 (98% of failures)
- `find_location_concentration` → top: LOC_A02 (100% of failures)
- `find_error_code_concentration` → top: ERR_OCR_LOW_CONFIDENCE (65%)
- `find_event_type_concentration` → top: ocr_read (99% of failures)
- `compare_event_type_duration` → ocr_read avg duration 254.4 ms → 596.8 ms (ratio 2.35)
- `correlate_retry_count_and_confidence` → r=-0.817 (strong negative correlation: retries track low confidence)
- `build_timeline` → 7 buckets; first failure 2026-07-03T16:06:53.500648+00:00
- `estimate_blast_radius` → 126 failures across 3 component(s), 107 correlation id(s) affected
- `generate_hypothesis` → confidence=high (evidence score 10)
- `generate_recommended_actions` → 5 actions

### Root-cause hypothesis

Localized read-quality degradation on OCR_GATE_02 at LOC_A02: confidence collapsed while retries and failures spiked on this component only (dominant error: ERR_OCR_LOW_CONFIDENCE). Most consistent with a physical/optical or component-level fault (e.g. dirty or misaligned camera, lighting change, or degraded sensor) rather than an upstream/systemic failure.

**Confidence level:** high (evidence score 10/10)

Reasoning:

- 98% of failures concentrate on a single component (OCR_GATE_02), indicating a localized fault rather than a systemic outage.
- Average confidence_score dropped by 0.40 vs baseline, consistent with degraded read quality.
- Average retry_count rose by 1.54 vs baseline.
- Retry count and confidence are strongly negatively correlated (r=-0.817), so retries are driven by low-quality reads.
- A single error code (ERR_OCR_LOW_CONFIDENCE) accounts for 65% of coded errors in the window.
- Average duration of ocr_read events in the window is 2.4x baseline (254 ms → 597 ms), a substantial latency increase.
- Window failures are homogeneous: 99% are ocr_read events.

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
