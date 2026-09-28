# Controlled integration test plan

Status: DESIGNED; every case below is NOT RUN. This is a future plan, not authorization to install/register/provision. Initial target is Ubuntu 22.04 x86_64, exact supplied PA 12.10 Debian build, non-production Harmony environment, dedicated agent group and temporary/test identity.

## Entry gates and isolation

Dharish supplies package/provenance, intended region/org/environment/group and naming policy, network/proxy requirement, approved disposable VM/access, selected registration strategy and explicit Phase 2 authorization. Secret values go through the approved provider, never chat. Obtain storage/secret handling acceptance before the selected mechanism is coded. Non-production qualification uses a digest-bound VERIFIED artifact exception; it does not require or grant production approval.

Record baseline image version, CPU/RAM/disk, clock, DNS/egress, service inventory, package inventory, effective user and framework/package digests. No business workloads. Use independent fresh test identities for manual and auto cases; do not delete working credentials to switch modes. Prefer resetting an unregistered baseline under test-owner control. Registered snapshots may be restored only with exclusive identity ownership; never run two copies.

## Test cases

| ID | Setup and action (future only) | Required evidence / pass criterion | Cleanup / failure handling |
| --- | --- | --- | --- |
| IT-001 Base installation | Verified exact .deb; inspect maintainer scripts/dependencies, then authorized install on clean target | Package name/full version/amd64; expected directories, file ownership, required components; capture prompts/autostart/Python dependency behavior | Preserve failed package state/log evidence; no blind purge or host-wide dependency upgrades |
| IT-002 Interactive registration | Pre-created test agent; native prompts, then start/restart | No secret echo; credentials metadata; intended Console identity reaches Running; actual service outputs/return codes | Preserve registered identity for lifecycle test or explicitly decommission later; no terminal secret recording |
| IT-003 Unattended registration | Separate clean identity; selected token/no-proxy candidate and approved materialization | register input consumed, credentials created with verified access, exact intended group, one new identity; fixtures and current cloud evidence | Remove only owned transient input; stop new attempt on failure; no fallback to argv secrets |
| IT-004 Authentication failure | Fresh test target; deliberately invalid test token via provider | No false success; actual auth marker/return semantics, error50 when proven, bounded timeout otherwise; secret-negative outputs | Stop pending registration before cleanup; revoke/disable only dedicated test material under owner control |
| IT-005 Network failure | Test-only reversible guest egress restriction to Harmony, preserving management/recovery access | Distinguish transport failure from auth; deadline honored; no false registered/healthy result | Test owner restores exact prior rule; confirm connectivity; no production/shared Azure network mutation |
| IT-006 Reboot | Successfully registered persistent test VM, deregistration disabled | Same cloud agent identity, credentials metadata persists, reconnect and services healthy after authorized reboot; later stop/start variant | Reboot outside active CSE; preserve identity; recovery evidence if it fails |
| IT-007 Agent restart | Successful test agent with no operations | Same identity, expected downtime then current Running; no duplicate registration or removed credentials | Reconcile actual state; do not rerun registration automatically |
| IT-008 Idempotent rerun | Same exact package/config on healthy target; repeat desired-state invocation | No reinstall, identity duplication, credential replacement or unnecessary restart; changed=false and fresh checks; concurrent request rejected/serialized | Preserve current service state; reject differing request with same idempotency key |
| IT-009 Existing credentials | Test separately healthy existing, deliberately deregistered stale, mismatched identity and dual-file residue | Healthy preserved; uncertain/stale/collision fails with lifecycle action42; no contents exported and no blind deletion | Recovery is a separate reviewed action; no cloned live identity |
| IT-010 Registration timeout | Fresh target; controlled unreachable/delayed registration beyond small test deadline | Exit52, last successful stage retained, null unknown health, attempt stopped, input cleaned; no late registration after timeout | Restore network; inspect intended group for orphan; reconcile manually before rerun |

IT-003 qualification also needs a rotation/inactivation/deletion experiment with the dedicated registration token: observe new registration and existing reconnect separately. No assumed TTL or revocation propagation. If proxy is required, IT-002 establishes the proxy baseline and IT-003 uses a separately qualified secure Mode B path; automatic registration is rejected before secret retrieval. Add controlled TLS/proxy negative variants to IT-005, without weakening certificate verification. Package input/output formats and service-account permissions are required evidence, not inferred defaults.

## Evidence collection contract

Each case produces a manifest with test/run ID, UTC start/end, target identity, image/framework/package versions and digests, action, expectation, observed result, exit category, last stage, cleanup result and reviewer. All fixture identifiers are synthetic or sanitized before repository use.

Capture restricted, reviewed excerpts from `/opt/jitterbit/log/Installer.log` and `/opt/jitterbit/log/jitterbit-agent.log` (J11), exact `jitterbit status` output/exit status, Support Tools launch/help and inner service-status/connection-check observations (J18), installed package metadata, selected system-service state properties, file existence/type/owner/group/mode/size/mtime, and process **names/PIDs/UIDs only**. Do not collect process command lines/environments, credentials.txt/register.json contents, private keys, tokens, shell traces or arbitrary config dumps. Validate that evidence paths themselves contain no secrets.

Vendor logs can contain secrets: filter at the collection boundary and keep unavoidable original product logs only on the restricted test host under retention policy. Do not copy raw logs to Git, Blob results or chat. Do not automatically run generate-report/zip-logs; inspect scope and redact first. Evidence output must fail closed if secret-negative checks detect test canaries. Keep the complete artifact privately; CSE's status tail cannot substitute for evidence.

Capture baseline log offsets and separate historical data from the current attempt. Record native process/inner-command codes independently. Turn real sanitized positive and negative observations into versioned deterministic fixtures only after review; reject unknown patterns. A passing exit code alone is not enough if a tool prints a failing component status.

## Exit and acceptance

All ten cases pass for the selected target/profile, with no secret leaks, duplicate identities, infinite waits or cleanup residues. Manual Console confirmation is labeled manual and does not qualify an automated cloud-status provider. Automated COMPLETE remains blocked until that provider or an explicitly reviewed alternative evidence contract is established. Production qualification additionally requires support/lifecycle, operation smoke tests, retention/rotation and deployment governance approval.

Azure wrapper qualification is a later, separately authorized integration exercise: actual caller contract, private Blob/Key Vault identity access, CSE UID/handler version, bounded failure/rerun and correlated result transport. This plan does not provision the test VM. Decommission test identities and tokens only through the test owner's authorized cleanup plan; retain sanitized evidence.
