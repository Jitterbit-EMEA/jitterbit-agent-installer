# JBPA release notes

## 1.0.0-rc9

Added the bundled `bin/jbpa-install` customer entrypoint. One invocation now prepares the runtime, imports a single private JSON document or prompts for Harmony details, presents/accepts the PA version, runs preflight and installation, and verifies the private result against current package, connection and services. A recognized Harmony capacity failure yields a customer-readable next step and private result path. A synthetic 10-success/11th-failure regression exercises that path without consuming live Harmony slots; see the capacity test report (source repository). RC9 has not been live-installed; the designated QA agent remains healthy.

## 1.0.0-rc8

Added one schema-validated, root-only JSON credential document for the customer launcher and direct local-JSON secret provider. The guided setup writes that document; unattended setup stages one file. `jbpa-customer verify` summarizes the latest successful install result and checks the current package, version, connection and core services. Known Harmony group/organization capacity errors now have a distinct result code. Existing local-file configurations remain supported. RC8 has offline validation only; RC7's live install evidence does not transfer automatically. Complete local uninstall still does not delete a Harmony agent record.

> Phase 3B scope correction: JBPA does not provision VMs. `azure/provisioning` and `bin/jbpa-azure` are NON_PRODUCTION / DEVELOPMENT_TEST_HARNESS / NOT_PART_OF_JBPA_RUNTIME. Historical evidence below is retained. The canonical production boundary is the [external orchestrator contract](external-orchestrator-contract.md); the external tool owns infrastructure.


## 1.0.0-rc2

- Added explicit forwarding of the existing qualification override through the packaged bootstrap and Azure caller boolean `allowUnqualified`.
- Qualification enforcement remains enabled by default. The override affects only qualification policy and requires controlled-test authorization; artifact, platform, configuration, security, registration and health validations remain active.
- Preserved exact package/platform qualification: dynamic latest cannot inherit qualification from another package version under the same logical release.
- Added audit metadata under existing result `details.qualification`; schema remains 1.0.
- Included the release bootstrap and settings example in the packaged distribution. No Jitterbit lifecycle implementation changed. No live Ubuntu 22.04 qualification or Azure dispatch occurred.

rc1 remains immutable historical evidence. RC2 is QA-only and does not promote PA artifact approval or production readiness.

## 1.0.0-rc3

Added first-class standalone REINSTALL using the existing complete removal and fresh installation workflows under one host lock. Added canonical structured host readiness shared by validate/INSTALL/REINSTALL, bounded probes, operational free-space thresholds and explicit unknown/blocking semantics. Results remain schema 1.0 through additive optional details; manifest/version output exposes capabilities. No infrastructure provisioning functionality is added; external orchestrator ownership is unchanged. RC2 remains immutable historical evidence. No new live qualification is claimed.

## 1.0.0-rc4

Added a protected local-file credential provider for customer VMs without Azure Managed Identity. Configuration and all secret references now select one provider consistently. Both standalone preflight and install resolve the same local files; unsafe permissions, links, missing and invalid files fail closed. Added a customer VM quickstart and packaged local-file QA example. Offline tests cover the provider and readiness. No live local-file PA installation, Ubuntu 22.04 qualification, or production artifact approval is claimed. RC3 remains immutable historical evidence.

## 1.0.0-rc5

Added `jbpa versions`/`jbpa version list` for all 19 governed catalogue entries and a TTY-only interactive install that displays exact observed package version and hash before requiring `INSTALL` confirmation. Added a same-major, in-place `jbpa upgrade` with existing-agent health and qualification guards, private configuration backup, graceful drain, exact package install, configuration preservation and post-upgrade identity/health checks. Major upgrades, downgrades and unknown latest packages stop for review. Offline tests pass; no new live install or upgrade qualification is claimed by this note. RC4 remains immutable historical evidence.

Subsequent QA evidence: the RC5 archive's local-file interactive `latest` installation completed on Ubuntu 24.04 with PA 12.10.1.1 on 2026-09-28. `upgrade --version latest` returned `ALREADY_CURRENT`, `changed: false`. The package-changing upgrade path remains unqualified live. See the customer runbook report (source repository). The published RC5 archive and digest were not changed after this test.

## 1.0.0-rc6

Added a single customer launcher with guided setup, hidden-token and local-file prompts, automatic Python runtime preparation, readable version list, install, upgrade and status commands. It delegates lifecycle actions to the existing JBPA CLI and retains its qualification gates. RC6 is a new QA candidate; RC5's live qualification does not automatically qualify the wrapper. SSH/SFTP, mTLS and proxy branches remain blocked.

Subsequent RC6 QA evidence: the archive digest was verified on the existing Ubuntu 24.04 QA VM. The packaged launcher prepared its runtime, listed 19 versions, reused protected local files without displaying the token, reported PA 12.10.1.1 installed/connected with core services healthy, and returned `ALREADY_CURRENT` with no package change through the upgrade command. It refused a duplicate install and the numbered menu operated correctly. A fresh RC6 launcher-driven PA installation was not performed; see the live launcher report (source repository).

## 1.0.0-rc7

Fixed the customer launcher's subprocess handling so JBPA's interactive package/version/hash confirmation appears on the operator's terminal while structured JSON remains captured for a concise result. The RC6 fresh-install attempt was cancelled before confirmation or package mutation when the hidden prompt was found. RC7 is a separate QA artifact; its fresh interactive test is reported separately.

Subsequent RC7 live result: the packaged menu completed a clean-host local-file interactive `latest` install on the designated Ubuntu 24.04 amd64 QA VM. PA 12.10.1.1 registered with Harmony and passed service/connection checks. The RC7 `upgrade --version latest` check returned `ALREADY_CURRENT`, `changed: false`. See the RC7 live test report (source repository). A package-changing upgrade, Ubuntu 22.04 and production approval remain open.
