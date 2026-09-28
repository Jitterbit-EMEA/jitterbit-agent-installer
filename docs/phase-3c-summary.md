# Phase 3C Summary

## Status

COMPLETE for implementation/release hardening. All 384 tests passed with zero failures; lint, schemas, credential scan, archive and packaged CLI checks passed. Final observed results are recorded in [validation evidence](../evidence/phase-3c/validation.json). No live qualification or infrastructure provisioning occurred.

## RC2

1.0.0-rc2 remains immutable. Archive, sidecar and staged manifest are compared with evidence/phase-3c/rc2-before.json. Expected archive SHA-256 is 68fa05cc43577a15f948c81a6e56e8d2b725d66d969934ec3f2eb6316e3266da. No rebuild or overwrite.

## Standalone REINSTALL

`jbpa reinstall --config PATH --version VERSION --non-interactive --result-file NEW_PATH` is a first-class operation. `--dry-run` reports a non-mutating plan; explicit `--controlled-test --allow-unqualified` supports controlled target qualification. Supported starts are registered/unregistered installed agents and CLEAN_HOST; clean start continues as fresh install. Partial/unknown state is rejected.

JBPA performs shared readiness, target artifact/approval verification before removal, one outer shared host lock, tested TranDb drain/provider and complete uninstall, independent clean-host confirmation, then normal install with pinned bytes. Existing fresh registration, initial synchronization and core health gates remain unchanged. Failure stops the lifecycle and preserves last successful state. Explicit force uses existing policy; no automatic force or retry. Non-secret prior/new observed names/version are recorded when available; absent numeric IDs remain unknown. Fresh local registration is proved independently of numerical Harmony identity difference.

## Host Preflight

One canonical `host_readiness.run` serves validate/INSTALL/REINSTALL. It covers actual OS/version/codename/kernel, amd64, privilege, dpkg audit/locks, existing-metadata dependency simulation, platform CPU/memory/disk policy, operational free space, bounded configured DNS/TLS, synchronization, existing secret-provider authentication/reference validation and existing product-state classification. No credentials contents are read for discovery and no secret values enter results.

PASS/WARN/FAIL/NOT_APPLICABLE/UNCONFIRMED plus a blocking flag are preserved for each check. Blocking failures or unconfirmed checks yield FAIL. Nonblocking warnings yield PASS_WITH_WARNINGS. Dry-run skips network/secret retrieval explicitly; no unknown becomes PASS. Root/sudo capability is observed without automatic escalation. Agent Services authentication remains a mandatory post-registration product gate, not a fabricated preflight PASS. See [preflight contract](preflight-contract.md).

## External Handoff and Schema

The request schema permits rc2 and rc3; REINSTALL is supported only for rc3. Generic caller forwards one reinstall command rather than composing removal/install. Core schema 1.0 remains: additive optional `details.preflight` and `details.reinstall` retain compatibility. Manifest exposes deterministic capabilities; `jbpa version` exposes the same operation set. No Azure infrastructure fields are required.

## RC3

1.0.0-rc3 is the new runtime release: [archive](../dist/jbpa-1.0.0-rc3.tar.gz), SHA-256 `4b06e3715cb5faf3472354934fc12c04b54c7febe25d98f47bf1f038075ad90e`, [manifest](../dist/jbpa-1.0.0-rc3/release-manifest.json). Final archive hash, manifest, file count and packaged CLI results are recorded in evidence/phase-3c. Runtime package excludes development provisioning/handoff tools. Associated runtime documentation and schemas are included. See [regression comparison](regressions/jbpa-1.0.0-rc3-vs-rc2.md).

## Tests

Previous baseline 307; final 384 passed, 0 failed (77 additional tests). Focused preflight/reinstall/caller tests cover positive, failure, unknown, dry-run, target-policy and lock cases. Final passed count, lint/schema/credential scan and archive verification results are recorded in validation evidence. ShellCheck/shfmt availability is reported separately.

## Production Readiness and Next Action

REINSTALL: IMPLEMENTED / MOCK-TESTED. Host readiness: IMPLEMENTED / MOCK/LOCAL TESTED. No Ubuntu live execution is claimed. GATE-10 Ubuntu 22.04 PENDING; GATE-13 External AI Orchestrator → JBPA Handoff PENDING LIVE TEST. JBPA starts at VM_ALREADY_PROVISIONED; infrastructure remains externally owned.

Next action is immutable RC3 via a separately controlled external tool on a pre-provisioned Ubuntu 22.04 amd64 host, first INSTALL qualification and then REINSTALL after preserving installation evidence. PA target 12.10.1.1 remains QA_TEST_ONLY / LOCALLY_CALCULATED; first run requires explicit qualification override. Enterprise deferrals and Harmony record deletion remain unchanged.
