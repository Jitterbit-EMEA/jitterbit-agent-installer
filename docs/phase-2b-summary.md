# Phase 2B Summary

## Status

PARTIAL. The Azure-facing bootstrap and secret provider are implemented and tested locally, and the supplied VM's Managed Identity can read the seven JBLAB secrets. Live PA 12.10 validation still needs an approved artifact digest and Ubuntu 22.04 target; production Azure dispatch has not been connected.

## Azure Key Vault Provider

Implemented through IMDS and the Key Vault Get Secret API with fixed, sanitized failures. No secret value is accepted in config.

## Managed Identity

Implemented in code and live-validated on the supplied VM. Its initial IMDS HTTP 400 was resolved by enabling a system-assigned identity and assigning secret-level read access for the seven JBLAB references. See [VM identity evidence](../evidence/pa-12.10.1.1/vm-managed-identity.md).

## Azure Bootstrap Integration

`bin/jbpa-bootstrap`, a hash-verifying Custom Script wrapper, CSE settings example, and offline release builder are present. The separately authored provisioning agent hook has not been connected or deployed.

## Production Configuration Model

Non-secret YAML and secret references belong in `/etc/jbpa/agent.yaml`; token values remain in Key Vault. The framework release, state/results and Jitterbit product files have separate ownership.

## Artifact Approval Gate

The user-supplied PA 12.10.1.1 URL is catalogued. The vendor response header and downloaded bytes agree on SHA-256, and Debian Package/Version/Architecture fields match. Phase 2C later classified that local digest as `APPROVED_FOR_TEST` for Ubuntu 24.04 only. The production path still returns `ARTIFACT_NOT_APPROVED` before secret retrieval or package mutation. See [artifact intake](../evidence/pa-12.10.1.1/artifact-intake.md) and the [Phase 2C summary](phase-2c-summary.md).

## Secret Handling

The token is resolved in memory, written only to the native `register.json` input when installation proceeds, removed after conclusive success, and cleared from the `Secret` wrapper. Error/result tests and repository scans check for leakage.

## Filesystem Hardening

Atomic mode-0600 registration-file creation with `jitterbit:jitterbit` ownership is tested with a synthetic local filesystem. Live PA 12.10 ownership validation is pending.

## Optional JKS Branch

Enabled configuration returns `JKS_CONFIGURATION_FAILED` until its noninteractive import and rollback contract is qualified.

## Optional SSH Branch

Enabled configuration returns `SSH_CONFIGURATION_FAILED` until product configuration behavior is qualified.

## Optional SSL Branch

Enabled configuration returns `SSL_CONFIGURATION_FAILED` until product configuration behavior is qualified.

## Proxy Handling

The tested no-proxy path is preserved. Enabled proxy returns `REGISTRATION_MODE_INCOMPATIBLE_WITH_PROXY`.

## Disposable VM Regression Harness

`bin/jbpa-regression` captures sanitized runtime facts and compares them with the PA 12.9.2.2 contract. The supplied VM was probed read-only and is Ubuntu 24.04 with PA 12.9.2.2 already registered; it cannot establish a PA 12.10/Ubuntu 22.04 pass.

## Tests

On 2026-09-23, `./scripts/test.sh` passed 118 tests with zero failures. `./scripts/lint.sh` passed Ruff, formatting, yamllint, Bash syntax, schema/example/link checks and the bounded repository credential scan (87 files). ShellCheck and shfmt were unavailable and skipped. The legacy CLI validate and diagnostics commands exited 0 while reporting the macOS host as unsupported; legacy and production dry-runs exited 10 (`UNSUPPORTED_OS`) as expected. Unit tests use synthetic secrets and never call a real vault. No PA 12.10 package or Harmony registration was executed.

## Remaining External Inputs

Independent PA 12.10.1.1 SHA-256; fresh Ubuntu 22.04 target; validation that the retrieved JBLAB values match the qualified registration contract; actual provisioning-agent integration source. The [JBLAB reference-only config](../config/agent.jblab.example.yaml) removes the need to commit Harmony values. The current Ubuntu 24.04 VM's Managed Identity can read all seven referenced values.

## PA 12.10 Readiness

NOT READY for the required Ubuntu 22.04 live regression.

## Production Readiness Gates

See [production readiness](production-readiness.md).
