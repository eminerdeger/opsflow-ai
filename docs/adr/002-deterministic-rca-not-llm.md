# ADR 002 — Deterministic RCA instead of an LLM agent for the MVP

- **Status:** Accepted
- **Date:** 2026-07-03

## Context

The diagnosis layer must turn a detected anomaly window into an incident report with
a root-cause hypothesis. An LLM-driven agent is the fashionable choice, but this MVP
must be reproducible, cheap to run, honest about what it knows, and free of paid API
dependencies (project rule: no paid LLM APIs).

## Decision

Implement RCA as a **deterministic, tool-style diagnostic workflow**: a fixed
pipeline of pure evidence-gathering functions (baseline comparison, component /
location / error-code concentration, retry↔confidence correlation, timeline, blast
radius) feeding a rule-based hypothesis engine. Evidence is scored 0–7 and mapped to
a low/medium/high confidence level; the selected failure-mode template cites only
computed numbers. The full tool-invocation trace is printed in the report.

The architecture uses discrete diagnostic tools with logged invocations. Future
versions may explore optional planner components over the same tools, but the MVP
intentionally remains deterministic, rule-based, and is never described as an LLM
agent.

## Consequences

- Reports are reproducible byte-for-byte for a given input, fully testable in pytest,
  and cost nothing to generate.
- Every claim traces to evidence in the data; the system cannot hallucinate causes.
- The trade-off is bounded expressiveness: the engine only recognizes failure modes
  it has templates for and says so explicitly when evidence does not localize a fault.
- Honest naming ("deterministic diagnostic workflow", not "AI agent") is a binding
  wording rule (CLAUDE.md rule 7).
