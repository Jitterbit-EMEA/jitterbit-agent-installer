# Phase 3D Summary

## Status

PARTIAL — external SSH handoff implementation and synthetic qualification are complete. Live Ubuntu 22.04 qualification is blocked pending the pre-provisioned host target, approved access and agent configuration/secret references. No live INSTALL or REINSTALL was attempted. The existing Ubuntu 24.04 QA host and agent 646830 were not touched.

## RC3

Immutable JBPA `1.0.0-rc3` archive: `dist/jbpa-1.0.0-rc3.tar.gz`. Approved SHA-256: `4b06e3715cb5faf3472354934fc12c04b54c7febe25d98f47bf1f038075ad90e`. Local verification passed; see [local verification](../evidence/phase-3d/ubuntu-22.04/rc3-verification.yaml). Host SHA-256: NOT_RUN. RC3 archive and sidecar were not modified or rebuilt.

## External Caller

The separate [SSH handoff](../tools/handoff/README.md) now implements strict pinned-host-key SSH delivery, on-host RC3 hash and manifest verification, canonical preflight, one JBPA lifecycle invocation per request, structured result retrieval, schema validation and generic result consumption. It does not provision a VM or parse vendor logs. The four new tests use a synthetic transport and do not constitute GATE-13 live evidence.

## Pre-Provisioned Host

NOT_PROVIDED. OS, codename, kernel, architecture, vCPU, memory, disk and initial host state are NOT_OBSERVED.

## INSTALL Preflight

NOT_RUN. All checks, warnings and `CLEAN_HOST` confirmation remain unobserved.

## INSTALL

NOT_RUN. Requested logical PA version is `12.10`; expected resolution `12.10.1.1` remains unverified on Ubuntu 22.04. The first run must use `allowUnqualified=true` and `controlledTest=true`.

## PA Artifact

Host package identity and hash: NOT_VERIFIED. The existing QA-only locally calculated SHA-256 is `604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8`; it is not production approved.

## Registration

NOT_RUN. No fresh credentials, register input, agent ID or group observed.

## Harmony Authentication

NOT_RUN.

## Agent Services

NOT_RUN.

## Initial Synchronization

NOT_RUN.

## INSTALL Health

NOT_RUN. Core services and connection-check unobserved.

## INSTALL Result Handoff

Synthetic test PASS; live process exit, result retrieval and caller consumption NOT_RUN.

## REINSTALL Preflight

NOT_RUN. `AGENT_INSTALLED_REGISTERED` starting state unobserved.

## Drain

NOT_RUN. Active operations and drain timeline unavailable.

## Uninstall

NOT_RUN.

## Clean Host

NOT_RUN.

## Fresh Install

NOT_RUN.

## Fresh Registration

NOT_RUN. Old/new agent identity unavailable.

## REINSTALL Health

NOT_RUN.

## REINSTALL Result Handoff

Synthetic one-operation test PASS; live process exit, result retrieval and caller consumption NOT_RUN.

## Ubuntu 22.04 Runtime Contract

NOT_OBSERVED. No Ubuntu 24.04 runtime observations were copied into a 22.04 contract.

## Ubuntu 22.04 vs 24.04

NOT_CLASSIFIED. A comparison requires observed Ubuntu 22.04 evidence.

## Qualification Promotion

NOT_PROMOTED. Source qualification remains unchanged. RC3 remains immutable; a later RC4 or separately governed release would be required to package any live qualification changes.

## Production Gates

GATE-10 Ubuntu 22.04: PENDING_LIVE_TEST. GATE-13 external orchestrator handoff: PENDING_LIVE_TEST. Standalone REINSTALL and INSTALL/REINSTALL host readiness: NOT_TESTED_LIVE.

## Tests

Previous baseline: 384 passing. Current validation: 390 passing, zero failures. Six SSH handoff and guest-delivery tests were added. Lint, formatting, schemas, examples, Markdown links, bounded credential scan and archive validation passed. Shellcheck and shfmt were unavailable. See [validation evidence](../evidence/phase-3d/ubuntu-22.04/local-handoff-validation.yaml).

## Final Host State

UNKNOWN. No Ubuntu 22.04 host was accessed. The existing Ubuntu 24.04 comparison host was not modified.

## Remaining Production Work

Provide a pre-provisioned Ubuntu 22.04 amd64 host address, approved SSH or equivalent access with pinned host key, and non-secret agent configuration/secret references. Run and freeze live INSTALL evidence before first-class REINSTALL. Artifact approval, production sizing, true custom CA, SSH/SFTP, mTLS, proxy and Harmony-side deletion remain separately pending under their existing governance classifications.
