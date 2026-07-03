# ADR 001 — Clean-room, synthetic-only rebuild

- **Status:** Accepted
- **Date:** 2026-07-03

## Context

This project demonstrates operational-data-platform skills (event pipelines, anomaly
detection, root-cause analysis) in a public portfolio repository. The author has
professional experience with real systems of this kind, but nothing from any employer
— data, logs, configs, identifiers, screenshots, or code — may appear here.

## Decision

Build the platform from scratch as a **clean-room rebuild based on architectural
knowledge only**, with a hard synthetic-only rule:

- All data is produced by `opsflow generate-events` (seeded, deterministic).
- No real company names, site names, hostnames, IPs, usernames, table names,
  filesystem paths, or credentials anywhere in the repo. Identifiers are generic
  synthetic IDs (`LOC_A01`, `OCR_GATE_02`, `ROUTER_01`).
- Local dev credentials (`opsflow_local_dev`) are throwaway values for a localhost
  container only.
- These rules are binding and codified in CLAUDE.md; a sensitive-string audit is part
  of the release checklist.

## Consequences

- The repo is safe to publish and share without legal or confidentiality risk.
- Scenario realism is bounded: values are chosen to be plausible, not calibrated
  against any real system (documented in ASSUMPTIONS.md).
- Synthetic generation with injected ground truth (`metadata.injected_anomaly`)
  doubles as a test oracle, making the detection and RCA layers properly testable —
  a benefit real data rarely offers.
