# Phase 2G Summary

## Status

COMPLETE for the scoped QA release candidate. All acceptance controls are implemented and validated locally; this is not production approval or a new live lifecycle certification. The QA VM and its registered agent were not changed. No historical bulk intake or installation ran. Earlier evidence and phase reports remain preserved.

## JBPA Version

JBPA 1.0.0-rc1, RELEASE_CANDIDATE_QA. Canonical source: src/jbpa/__init__.py. Config schema 1 (reported 1.0), RC result 1.0, catalogue 2 (reported 2.0), runtime contract 1.0, artifact manifest 1.0. Legacy operation schemas remain preserved under details or standalone utilities. Bootstrap failures before framework initialization use jbpa=null in the RC envelope.

## Dynamic Latest Endpoint

The exact endpoint is https://login.jitterbit.com/jitterbit-cloud-mgmt-console/download/latest/agent/linuxdebian?architecture=x64. It is DYNAMIC_MUTABLE and absent from static aliases. Explicit metadata inspection on 2026-09-26T11:48:30.930494+00:00 resolved to 12.10.1.1 / logical 12.10, byte size 660897206, SHA-256 604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8. The observed effective URL is https://download.jitterbit.com/12.10gdhdye6ehwgs5627u3udhdyd/jitterbit-agent_12.10.1.1_amd64.deb. Content-Type was application/octet-stream; Content-Disposition filename was not supplied. dpkg-deb confirmed jitterbit-agent, amd64, Depends odbcinst and unixodbc. Catalogue match true, scoped runtime qualification TESTED_LIVE, production_approved=false.

The first local attempt had no validated output: dpkg-deb was absent and a result path directly under the public temporary directory failed the private-result writer. The Debian inspection tool was installed, a private result directory was used, and the successful explicit inspection is retained. A later local-file verification initially failed while its optional argument was being wired; its fixed failure result remains alongside the final successful verification. No PA scripts were executed by these inspections. The temporary downloaded package cache was removed after the final offline verification; only metadata/results were retained.

## Pinned Version Catalogue

Exactly 19 pinned logical releases and one dynamic latest entry, programmatically checked. Full logical/package identities, exact user-supplied URLs, filenames and architectures are preserved. The governed expected_pinned_count field permits future onboarding through data changes. Duplicate/mismatched identities and invalid aliases fail closed.

## Tested Versions

12.10 / 12.10.1.1: Ubuntu 24.04.5 amd64, native .deb, no proxy, token register.json. Core install/registration/initial health, graceful local lifecycle/reinstall and scoped endpoint trust retain TESTED_LIVE evidence. The functional sizing exception does not establish production sizing.

12.9 / 12.9.2.2: scoped Ubuntu 24.04 installation/registration/initial health evidence. No drain, full uninstall/reinstall or enterprise qualification is transferred from 12.10.

## Available Unqualified Versions

17 releases: 12.8, 12.7, 12.6, 12.5, 12.4, 11.59, 11.58, 11.57, 11.56, 11.55, 11.53, 11.52, 11.51, 11.50, 11.49, 11.48, 11.47. URLs are catalogued; metadata intake and live qualification remain unexecuted. See [the matrix](version-qualification-matrix.md).

## Artifact Integrity

PA 12.10.1.1 digest remains 604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8, LOCALLY_CALCULATED, QA only. The latest response and retained file independently rehashed to that same governed local digest. This is not independent vendor provenance. Metadata manifests are schema checked and immutable by package/hash; changed pinned bytes return ARTIFACT_CHANGED. Cache names include exact package version and SHA, cached bytes are rehashed. --file verifies retained pinned bytes offline; it cannot resolve mutable latest. Packages are bounded to 2 GiB and temporary batch files are serially cleaned up.

## Version Resolution

Logical version, exact package and governed alias resolution are offline. Dynamic latest is requested explicitly, checked for HTTPS redirect/auth/content behavior and validated with dpkg-deb. HTML/non-DEB responses fail. Latest install pins one inspected file/hash for the run and delegates exact identity/hash verification to the existing native workflow. An unqualified exact platform is VERSION_NOT_QUALIFIED; unqualified latest is LATEST_VERSION_NOT_QUALIFIED. Explicit allow-unqualified plus controlled-test is EXPERIMENTAL_VERSION_TEST. Denied/blocked entries cannot be overridden. Production additionally requires approved governance, PRODUCTION_APPROVED status and INDEPENDENTLY_VERIFIED integrity.

## Version Aliases

recommended, latest-tested and latest-available-pinned all resolve to logical 12.10. Neither intake nor regression modifies aliases or qualification. latest is only the mutable source.

## CLI

install, uninstall, health, diagnostics, validate, enterprise, artifact, regression and version are consolidated under bin/jbpa. Existing standalone utilities retain legacy formats. RC output is one structured envelope plus process exit code; detailed operation results remain under details. Bare health is LOCAL_ONLY; --profile or validated expected-identity config reaches the existing composite evaluator. Uninstall --config consumes bounded timeouts with explicit CLI overrides. Force is never implicit.

## Runtime Contracts

contracts/12.10.1.1.yaml and contracts/12.9.2.2.yaml are versioned, schema validated and evidence referenced. The 12.10 baseline retains dependencies, silent_install, root/Resources/register/credentials/JRE/truststore/PostgreSQL/log paths, registration markers, health profiles, service/provider contract and drain/uninstall behavior. The 12.9 contract deliberately omits untested later-health/lifecycle scope. No fake historical live contracts were created.

## Regression Harness

BASIC requires --live, explicit config and a clean disposable target, then validates artifact, installs/registers/health-checks via the existing workflow and captures runtime observations. FULL_LIFECYCLE additionally drains/uninstalls/verifies clean/reinstalls using the same resolved bytes. Both were tested with mocks; neither ran against the QA VM in this phase. Observed initial runtime comparison returns CONTRACT_UNCHANGED, CONTRACT_COMPATIBLE_MINOR_CHANGES for timing-only observations, CONTRACT_CHANGED or REGRESSION_FAILED. Timing changes are not a performance conclusion. Restart/truststore behavior remains explicitly unobserved by BASIC; full lifecycle records removal/reinstall results but does not replace branch qualification. Promotion is manual.

## Release Packaging

Final archive SHA-256: 5a18ba2bbc87efdb5a9aa671a1fa6d87575f2446981d00814c27b847efc7eacd. Build runs source validation, all tests, lint/format/YAML/schemas/catalogue/contracts, metadata validation and bounded credential scans before staging. Bundle contains bin, lib, config, schemas, contracts, curated operational docs, README, pinned Python requirements, release-manifest.json and SHA256SUMS. QA evidence, raw logs, credentials, register.json, private keys and PA installers are excluded. Archive metadata uses root:root ownership, non-writable group/world modes and executable CLI. Verification validates archive digest, bounded safe tar entries, exact file set/hashes, manifest/catalogue/contracts, schema versions and governance metadata. 75 files verified. The packaged CLI version command succeeded without resolving latest. No release signing is claimed.

## Azure AI Agent Contract

[Contract](azure-ai-agent-contract.md) and azure/custom-script/release-bootstrap.sh provide framework acquisition, digest/safe extraction, isolated venv/pinned dependency setup, complete release verification, config invocation and structured results. Failure-before-runtime cases are tested for incorrect digest and unsafe archive, with fixed RELEASE_ERROR JSON. Python 3.10+/venv and an approved dependency index remain prerequisites; wheels/interpreter are not bundled. Product lifecycle logic remains in JBPA. The separately authored provisioning agent and live CSE dispatch were not changed or certified.

## Security Review

[Focused security review](security-review.md) covers registration/Key Vault secrets, credentials/register input, TranDb/keytool environments, artifact/latest URLs, argv/stdin controls, temporary files/permissions, immutable results, packaging and redaction. The bounded source/bundle scans pass. This is not independent penetration testing or organizational security approval. Opaque vendor URL paths are metadata, not classified as credentials. Inspection records provenance, while normal version/list output avoids repeating URLs.

## Production Readiness

Core lifecycle and the exact PA 12.10 Ubuntu 24.04.5 functional tuple remain TESTED_LIVE; PA 12.9 retains scoped evidence. Ubuntu 22.04 is NOT_TESTED. Java truststore / explicit endpoint trust is TESTED_LIVE for a CA:FALSE certificate; true CUSTOM_CA is NOT_TESTED_WITH_CURRENT_CERTIFICATE. SSH is DEFERRED_NO_TEST_MATERIAL, SSL DEFERRED_NO_PRIVATE_KEY_OR_MTLS_ENDPOINT, proxy DEFERRED_NO_PROXY_TEST_ENVIRONMENT. Production sizing, independent artifact promotion, security approval, release signing/dependency supply chain and live Azure integration remain pending. Harmony record deletion is not automated and historical old/new ID distinctness remains unverified.

## Tests

Previous baseline: 178 passed, zero failures. Final: 223 passed, zero failures (45 additional cases). Ruff lint/format, YAML, Bash syntax, schemas, catalogue/contracts, metadata and bounded credential scan pass. ShellCheck and shfmt are unavailable and were explicitly skipped. Mock regression covers basic/full composition, once-resolved latest bytes, dirty-host blocking and experimental classification. Negative artifact/release/bootstrap cases do not contact a live VM.

## Generated Release Artifacts

- [Archive](../dist/jbpa-1.0.0-rc1.tar.gz)
- [Archive digest](../dist/jbpa-1.0.0-rc1.tar.gz.sha256)
- [Manifest](../dist/jbpa-1.0.0-rc1/release-manifest.json)
- [File hashes](../dist/jbpa-1.0.0-rc1/SHA256SUMS)
- [Version matrix](version-qualification-matrix.md)
- [Security review](security-review.md)
- [Runbooks](README.md)
- [Latest inspection](../evidence/phase-2g/latest-inspection.json)
- [Pinned file verification](../evidence/phase-2g/pinned-verification-final.json)
- [Release verification](../evidence/phase-2g/release-verification.json)
- [Bundled version command](../evidence/phase-2g/bundled-version.json)

## Remaining Work

Review the release/hash and organizational production gates, then wire the Azure provisioning agent to the documented command/JSON contract. Qualify Ubuntu 22.04 on a fresh approved target. Obtain independent production artifact provenance, production sizing evidence, signed/trusted distribution and dependency supply-chain approval. Qualify true custom CA/SSH/mTLS/proxy only when suitable QA material and endpoints are available. Future historical intake or live regression requires an explicit operation; no mass testing is implied.
