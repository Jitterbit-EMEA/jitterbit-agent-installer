# JBPA release notes

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
