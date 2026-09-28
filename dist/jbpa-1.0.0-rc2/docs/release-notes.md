# JBPA release notes

## 1.0.0-rc2

- Added explicit forwarding of the existing qualification override through the packaged bootstrap and Azure caller boolean `allowUnqualified`.
- Qualification enforcement remains enabled by default. The override affects only qualification policy and requires controlled-test authorization; artifact, platform, configuration, security, registration and health validations remain active.
- Preserved exact package/platform qualification: dynamic latest cannot inherit qualification from another package version under the same logical release.
- Added audit metadata under existing result `details.qualification`; schema remains 1.0.
- Included the release bootstrap and settings example in the packaged distribution. No Jitterbit lifecycle implementation changed. No live Ubuntu 22.04 qualification or Azure dispatch occurred.

rc1 remains immutable historical evidence. RC2 is QA-only and does not promote PA artifact approval or production readiness.
