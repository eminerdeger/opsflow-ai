# Audit repo

Audit this repository against its constitution (CLAUDE.md):

1. **Security/synthetic-only**: scan the full repo (code, docs, sample data, configs)
   for anything that could be a real company name, hostname, IP, username, real
   filesystem path, credential, or non-synthetic identifier. Everything must use
   generic synthetic IDs.
2. **Scope discipline**: flag any over-engineering that violates the exclusions
   (Kubernetes, Kafka, Terraform, Prometheus, paid LLM APIs, meta-systems).
3. **Honest wording**: verify docs/reports describe the RCA as a deterministic
   tool-style workflow, never as an LLM agent.
4. **Runnability**: verify the P0 quickstart commands in README.md match the actual
   CLI, and that `pytest` passes.
5. Report findings as a prioritized list with file:line references. Fix nothing yet.
