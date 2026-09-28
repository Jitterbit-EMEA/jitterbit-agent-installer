# Phase 3A.1 Summary

RC2 corrects explicit qualification override forwarding without changing Jitterbit lifecycle code. The immutable rc1 archive, digest sidecar and release manifest are preserved and compared before/after. RC2's canonical version source is `src/jbpa/__init__.py`.

The bootstrap seventh positional argument is `false|true`, default false. True requires controlled-test; it forwards `--allow-unqualified` once using a Bash array. External callers use strict boolean `allowUnqualified`. Direct CLI and regression keep their existing flags. Exact package/platform qualification is enforced; latest cannot inherit qualification from a different package. Result schema 1.0 adds audit metadata under details.qualification and retains EXPERIMENTAL_VERSION_TEST for explicit unqualified execution.

Artifact hashes, DEB fields/architecture, OS preflight, config schemas, security, Managed Identity/Key Vault, dependencies, installation, registration and health remain enforced. No catalogue promotion or lifecycle changes occurred. Caller tests are mocks; invocation fixtures stop with a nonzero preflight code rather than fabricate installation success.

See [rc1 comparison](regressions/jbpa-1.0.0-rc2-vs-rc1.md), [release notes](release-notes.md), [bootstrap interface](azure-bootstrap.md), and [release evidence](../evidence/phase-3a.1/rc2-release-verification.yaml).

Release build and archive-derived CLI verification results are recorded in the evidence directory. Ubuntu 22.04 qualification and real Azure dispatch remain PENDING, GATE-10/PENDING and GATE-13/PENDING. Once RC2 verification passes, the next live action is the separate provisioning agent creating a fresh approved Ubuntu 22.04 amd64 target, dispatching the immutable rc2 release in controlled-test mode with allowUnqualified=true and consuming process exit plus result JSON. No live environment was supplied in this phase; no Azure or existing QA VM mutation occurred.

## Verified outcome

Phase 3A.1: COMPLETE. All 252 tests passed, zero failures; Ruff lint/format, Bash syntax, schemas/catalogue/contracts/metadata and bounded credential scan passed. ShellCheck and shfmt were unavailable and explicitly skipped.

RC1_IMMUTABILITY: PASS. Expected and actual archive SHA-256 remain `5a18ba2bbc87efdb5a9aa671a1fa6d87575f2446981d00814c27b847efc7eacd`; sidecar and manifest digests also match the pre-edit snapshot. No rc1 file was rebuilt or edited.

RC2 archive: [jbpa-1.0.0-rc2.tar.gz](../dist/jbpa-1.0.0-rc2.tar.gz), SHA-256 `68fa05cc43577a15f948c81a6e56e8d2b725d66d969934ec3f2eb6316e3266da`. [Manifest](../dist/jbpa-1.0.0-rc2/release-manifest.json) and [digest sidecar](../dist/jbpa-1.0.0-rc2.tar.gz.sha256) generated separately from rc1. Archive verification passed for 79 files. The archive-derived CLI reports 1.0.0-rc2; archive-derived bootstrap interface and Bash syntax checks passed. Version-aware release verifiers were used for each RC.

Only `__init__.py`, `release.py`, and `release_cli.py` differ among JBPA Python modules compared with the rc1 archive. Native lifecycle, registration, health, uninstall, enterprise, secret providers and regression implementation are byte-identical. Packaging/documentation/bootstrap/caller/test additions are scoped to the override handoff. Bootstrap and caller readiness: READY_FOR_LIVE_TEST; environment readiness remains external. No catalogue or approval promotion occurred.
