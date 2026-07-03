# Generate README

Regenerate or update README.md so it exactly matches the current state of the code:

1. Verify every command shown in the quickstart against the actual CLI
   (`python -m opsflow --help` and each subcommand's `--help`).
2. Keep the required sections: what OpsFlow AI is, why it exists, what it
   demonstrates, quickstart, P0 demo commands, architecture overview (Mermaid),
   the no-real-data statement, and the deterministic-RCA clarification.
3. Only document features that exist and pass tests today; planned work goes under
   Roadmap with its P-level.
4. Tone: serious platform project for a technical portfolio — concrete, no hype.
