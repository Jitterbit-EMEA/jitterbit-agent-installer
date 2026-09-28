# Phase 1.5 Summary

## Status

COMPLETE — evidence resolution, architecture reconciliation and Phase 2 readiness specification. Runtime remains Phase 1. No Jitterbit package was downloaded, inspected with dpkg, installed or registered; no real register.json was created; no Azure infrastructure was modified. Phase 0/1 content is preserved with current-decision addenda. Source, schemas, YAML, tests and scripts are unchanged.

## DEP-001 — Private Agent Artifact

Status: PARTIALLY_RESOLVED.

Evidence: Ubuntu Debian amd64 package and portal acquisition route documented (J01/J17); metadata inspection and approved private distribution designed in [artifact intake](artifact-intake.md).

Remaining requirement: actual PA12.10 package/full build and provenance, vendor integrity evidence if available or explicit provenance acceptance, mirror entitlement and package/dependency/service behavior. Final download URL authentication/expiry is unobserved. No invented digest or production approval.

## DEP-002 — Registration Automation

Status: PARTIALLY_RESOLVED.

Supported mechanisms identified in current documentation:

- Interactive jitterbit-config baseline.
- Parameterized jitterbit-config, including a credentials-file option whose format/security still needs verification.
- Native Linux register.json automatic registration; shared schema includes encrypted credentials or Agent Registration token.

Preferred candidate: token-based auto-registration for a no-proxy persistent VM, subject to native12.10 and materialization tests. This is REQUIRES_TEST, not production validated.

Proxy implications: automatic registration is documented as incompatible with proxies; use the manual/config-utility route when a Harmony proxy is required. Authenticated proxy automation remains blocked until a secure input channel is established.

Remaining validation: exact package capabilities, file owner/group/mode, transient secret policy, token expiry/revocation/reconnect behavior and safe cleanup. See [registration strategy](registration-strategy.md).

## DEP-003 — Registration Health

Status: PARTIALLY_RESOLVED.

Verified health signals: documented package/local service checks, credentials lifecycle, Agent Support Tools, main/installer log locations and Console Running state. These are documented signals, not locally executed product checks.

Unverified signals: exact current-build registration-success/failure patterns, dependable tool return codes/noninteractive interface, and supported current machine-readable Harmony status. No universal exact success string or qualified cloud-status API was established. Support Tools are documented through an interactive prompt; launcher success cannot substitute for inner-command success.

Recommended composite health gate: installed approved build, required services healthy, reconciled registration identity evidence, qualified connectivity, no current fatal registration error and current authoritative Harmony Running. Unknown cloud status must not become COMPLETE. Manual Console evidence may support tests but is labeled manual. See [health model](health-evidence.md).

## DEP-004 — Azure Integration

Status: PARTIALLY_RESOLVED.

Recommended orchestration: Custom Script Extension2.1+ primary bootstrap candidate; cloud-init for first-boot prerequisites; Managed Run Command for diagnostics/recovery or longer/sequenced execution. The [decision matrix](azure-integration-decision.md) records why this revises the Phase 0 preference.

Managed Identity design: initially system-assigned unless caller requirements dictate otherwise; scoped artifact-read and dedicated-vault secret-read roles, separate publisher and result transport privileges.

Artifact retrieval: approved immutable private Blob content with independent digest verification before executing bootstrap/framework code. No Harmony secrets in extension settings or command lines.

Remaining external integration dependency: actual provisioning author's source path/branch/commit or tool specification; guest readiness, identity/network validation and full correlated result transport. The inspected VNet-only CLI is not the missing VM implementation.

## Recommended Registration Architecture

Keep three explicit modes. Default candidate for the initial direct-egress persistent server is auto-register/access-token, deregistration disabled, identity preserved across restarts and reruns. Proxy-required targets select a qualified config-utility/assisted path. Existing unknown/stale credentials require explicit recovery, never blind deletion. Cloned registered images are excluded. Configuration changes are proposed in [schema change proposal](schema-change-proposal.md), not implemented.

## Recommended Artifact Architecture

Administrative retrieval → quarantined intake → metadata/provenance/integrity review → private versioned Blob → digest-bound catalogue review → controlled non-production qualification → explicit approval. Upload is not approval. VERIFIED lab qualification and production eligibility are separate. Lifecycle/immutability policies must preserve in-use and recovery artifacts.

## Security Findings

Plaintext password/encryption utility arguments violate the existing no-argv-secret policy. Key Vault does not remove exposure at the vendor handoff. register.json contains a bearer secret and needs an accepted, tested transient-file solution; restrictive permissions alone do not resolve the no-plaintext-persistence requirement. credentials.txt is product-managed encrypted identity and must be preserved, restricted and excluded from images/diagnostics. No fixed owner/group or token lifetime is invented. Vendor output/diagnostic archives and extension output are potential leak paths; collect only sanitized evidence.

## Phase 2 Test Requirements

[IT-001–010](integration-test-plan.md) cover base install, assisted/unattended registration, bad authentication, network failure, reboot, restart, idempotent rerun, existing credentials and timeout. Use an approved Ubuntu22.04 x64 disposable VM, exact PA12.10 build, dedicated non-production group and test identity. Capture safe metadata and reviewed log/tool evidence; never secret contents or process argv/environments. Token invalidation, proxy/TLS and crash-cleanup variants are specified. All live cases are NOT RUN.

[Phase 2 implementation specification](phase-2-implementation-spec.md) defines inputs, operations, outputs, errors, cleanup and states for each step; reconciles future reason codes with existing numeric exits; preserves last successful stage and honest unknown outcomes.

## Regression Validation

Tests: 76 passed, 0 failed; existing suite unchanged, including secret-negative and Ubuntu fixture cases.

Lint: available checks PASS; shellcheck/shfmt skipped because unavailable. Four schema definitions, actual YAML catalogues/example and documentation links validated.

Dry-run: PASS as a framework refusal check — actual macOS FAILED/10 (UNSUPPORTED_OS); Ubuntu fixture BLOCKED/22 (missing installer metadata). Neither is successful installation.

Diagnostics: DIAGNOSTICS/0; configuration validation VALIDATED/0; each actual CLI output conforms to result schema and retains changed=false and null runtime health.

Secret checks: existing redaction/leak tests and bounded repository credential-pattern scan PASS. This is not a comprehensive security audit. Dependency consistency PASS. Before/after SHA256 comparison: all 29 baseline implementation/config/test/script files unchanged. See [validation record](phase-1.5-validation.md).

## Remaining Blockers

1. Exact artifact and provenance/integrity/entitlement evidence.
2. Non-production Harmony target, test identity and approved VM availability.
3. Selected registration/network mode and accepted secret materialization policy.
4. Native build behavior, tool semantics and current registration/health fixtures; supported cloud-status contract for full unattended completion.
5. Actual Azure provisioning hook and integration validation for the Azure phase.

The [dependency register](dependencies.md) and [implementation matrix](implementation-matrix.md) distinguish documented, designed, implemented, mocked and untested functionality. No runtime feature was promoted to implemented merely because its documentation was found.

## Phase 2 Authorization Recommendation

NOT READY.

Reason: research/design is complete, but the user-defined entry gate still lacks the supplied package, non-production target, selected secure registration strategy and available integration test environment. Once those inputs and explicit Phase 2 authorization exist, controlled adapter development/testing can begin. The missing Azure hook need not block separately authorized portable testing on an existing VM, but it blocks actual Azure integration. Stop after Phase 1.5.
