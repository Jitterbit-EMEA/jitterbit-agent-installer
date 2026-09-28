# ADR-001: Python framework with thin Bash launchers

Accepted for Phase 1, 2026-09-22. Baseline: architecture.md proposed Python for structured data and small shell entry points.

Use Python >=3.10 for strict YAML, JSON Schema, typed provider contracts, centralized output and deterministic unit tests. Use PyYAML SafeLoader and jsonschema; use unittest from the standard library. Bash only locates the isolated interpreter and invokes the CLI. No shell handles secret payloads. A src/jbpa package replaces numerous shell forwarding modules to reduce coupling and duplicate serialization.

Phase 0 reconciliation: structural config validity is separate from installation readiness, so null vendor inputs validate but produce explicit blockers. Dry-run is not an installation success. No system log/result paths are written automatically; stdout carries JSON, stderr structured logs, and only explicit --result-file permits an artifact write. No .env loading or interactive credential collection yet; those options are deferred rather than silently implemented. The initial alias map is empty because package approval is pending. Host validation on macOS must truthfully fail platform compatibility; Ubuntu fixtures test the target logic without a public spoof-host switch.

Phase 0 documents remain evidence snapshots. Current executable behavior is described in developer-guide.md; no product facts were changed to fit code.
