# Phase 2 native Linux implementation summary

Status: PARTIAL. The exact evidence-qualified runtime workflow is implemented and tested with injected host behavior. Execution remains blocked until the package catalogue contains an approved artifact URL and trusted SHA-256 digest. PA 12.10 on Ubuntu 22.04 has not been regression-tested.

Implemented:

- Idempotent exact-version package detection, bounded apt lock waits, prerequisite installation, download, digest verification and Debian metadata checks.
- Native silent package installation and required product-path validation.
- Existing-identity protection, registration-state conflict detection and restrictive native register.json creation.
- One restart, delayed-log polling, explicit registration failures, composite Harmony/runtime success and local service validation.
- Secret clearing on every outcome and secret-free structured adapter results.
- Sanitized, hash-linked Prompt, Reference 1 and Reference 2 evidence artifacts.

The optional SSH, SSL and Java trust mutations fail closed because the supplied successful run did not qualify those configuration branches. Azure dispatch and production Key Vault integration remain separate work.

Validation: 92 unit tests passed, including the 76 baseline tests and 16 native workflow tests. Ruff, formatting, yamllint, Bash syntax, JSON Schema/link checks and the repository credential scan passed. ShellCheck and shfmt were unavailable and explicitly skipped.
