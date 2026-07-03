# Write tests

Add or extend pytest tests for: $ARGUMENTS

Rules for this repo:
- Use the deterministic fixtures in tests/conftest.py (fixed seed + fixed
  `start_time`) so tests never depend on wall-clock time.
- Test behavior through public entry points (generator, detector, DiagnosisAgent,
  CLI via click's CliRunner), not private helpers.
- For anomaly logic, always test both directions: the injected scenario is detected
  AND the baseline scenario produces no false positives.
- The detector/RCA must never read `metadata.injected_anomaly`; tests may use it as
  ground truth.
- Run `pytest` after writing; fix failures (up to 3 attempts) before finishing.
