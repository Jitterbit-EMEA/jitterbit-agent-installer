# Version qualification matrix

Current QA confirmation, 15 October 2026: all 20 exact pinned packages are Engineering-QA-verified, as relayed by the user. Provenance is recorded in [the confirmation](../evidence/engineering-qa/confirmation-2026-10-15.json). This confirmation is distinct from the local observations in the remaining columns.

Catalogue version 2: exactly one dynamic latest source and 20 pinned logical releases. Artifact metadata and runtime qualification are distinct. Availability is not compatibility or production approval.

| Logical | Package | Engineering QA | URL type | Metadata | SHA-256 | Ubuntu 24.04 | Ubuntu 22.04 | Core install | Registration | Lifecycle | Truststore | Overall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| latest | Resolved per request | Match exact pinned package; future versions excluded | DYNAMIC_MUTABLE | Explicit inspection only | Pin per run | Inherit exact resolved tuple | NOT_TESTED | Guarded | Guarded | No implicit test | No implicit test | Inherit catalogue or AVAILABLE_UNQUALIFIED |
| 12.11 | 12.11.3.2 | QA_VERIFIED | PINNED | METADATA_VERIFIED | 6e69a441c866ef2610aae603485ac82a05b711ccaca524f56c980458cb4907f0 | Single QA upgrade observed; formal qualification pending | NOT_TESTED | Fresh install NOT_TESTED | Existing identity retained in QA upgrade | Scoped upgrade observed | NOT_TESTED | QA_APPROVED |
| 12.10 | 12.10.1.1 | QA_VERIFIED | PINNED | VERIFIED | 604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8 | TESTED_LIVE (scoped) | NOT_TESTED | TESTED_LIVE | TESTED_LIVE | TESTED_LIVE | ENDPOINT_TRUST_TESTED_LIVE | TESTED_LIVE |
| 12.9 | 12.9.2.2 | QA_VERIFIED | PINNED | OBSERVED_LIVE | NOT_VERIFIED | TESTED_LIVE (scoped) | NOT_TESTED | TESTED_LIVE | TESTED_LIVE | NOT_TESTED | NOT_TESTED | TESTED_LIVE |
| 12.8 | 12.8.1.6 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 12.7 | 12.7.1.2 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 12.6 | 12.6.0.34 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 12.5 | 12.5.0.51 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 12.4 | 12.4.0.46 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 11.59 | 11.59.0.61 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 11.58 | 11.58.0.28 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 11.57 | 11.57.0.51 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 11.56 | 11.56.0.28 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 11.55 | 11.55.0.17 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 11.53 | 11.53.0.34 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 11.52 | 11.52.1.3 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 11.51 | 11.51.1.2 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 11.50 | 11.50.1.1 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 11.49 | 11.49.1.1 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 11.48 | 11.48.0.38 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |
| 11.47 | 11.47.0.61 | QA_VERIFIED | PINNED | NOT_INTAKEN | NOT_VERIFIED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | QA_APPROVED |

PA 12.10 digest is LOCALLY_CALCULATED and APPROVED_FOR_TEST_ONLY. PA 12.9 evidence covers installation/registration/initial health, not later drain/uninstall/reinstall/enterprise behavior. Ubuntu 24.04 qualification refers to the actual 24.04.5 VM for PA 12.10. No historical bulk intake or live test was performed in Phase 2G. True CUSTOM_CA is NOT_TESTED_WITH_CURRENT_CERTIFICATE (CA:FALSE).

Governed aliases: recommended = latest-tested = latest-available-pinned = 12.10. Updates require review; neither intake nor regression promotes them. The exact user-supplied URLs are retained in [the catalogue](../config/versions.yaml). Runtime contracts exist only for [12.10.1.1](../contracts/12.10.1.1.yaml) and [12.9.2.2](../contracts/12.9.2.2.yaml).

15 October 2026: [12.9.2.2 to 12.11.3.2 QA upgrade](upgrade-12.11.3.2-qa-validation.md) passed using the vendor-owned observer on the specifically authorized two-vCPU host. This does not qualify fresh 12.11 installation, other platforms, business operations, production sizing or production deployment. At that execution date, catalogue approval/qualification and recommended aliases were unchanged; the subsequent Engineering QA confirmation is recorded above.

All catalogue artifact statuses are now QA_APPROVED and approvals are approved_for_test. Locally TESTED_LIVE runtime classifications remain intact for 12.10/12.9; other overall classifications are QA_APPROVED, with explicit QA_VERIFIED Engineering provenance on every entry. Older descriptions of unqualified availability in dated reports are historical. This update does not claim local tests of all versions/platforms, manufacture missing package digests, rewrite immutable release archives or promote production approval. Platform-specific installation gates and controlled-QA requirements still apply.
