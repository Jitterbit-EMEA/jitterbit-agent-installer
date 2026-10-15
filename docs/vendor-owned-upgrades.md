# Vendor-owned upgrades and explicit recovery

Decision: 2026-10-14. JBPA orchestrates Jitterbit's supported installation/configuration behaviour; it must not replace that behaviour with its own deployment algorithm.

## Upgrade ownership

JBPA validates the exact artifact and eligibility, records a private configuration backup, drains active work, captures the runtime log cursor, and invokes the vendor package installer. The installer retains its normal post-install configuration restoration and startup behaviour. JBPA does not set `JITTERBIT_INSTALL_AUTO_START` to suppress startup, edit package scripts, restart from verification, extract/rebuild Axis, change Tomcat permissions, or restore configuration over the vendor's result.

The upgrade observer polls fresh runtime evidence from the pre-install cursor and performs fixed read-only application checks. It requires registration/request-flow evidence, core services, the expected version/identity, complete vendor-expanded Axis files and a valid local JsonEngine WSDL publishing `xmlToJson`. HTTP 200 with an error page is not readiness. These checks establish component readiness; they do not claim a Gmail test or business operation has passed.

The observer tolerates slow startup within the configured deadline. Missing, truncated or mismatched deployment files and unavailable application endpoints prevent `UPGRADE_COMPLETE`. On failure, return the package-changed state, safe diagnostic evidence and backup reference; do not automatically repair, reinstall, downgrade or retry installation. Package registration and port reachability alone are insufficient success criteria. An externally disabled vendor autostart remains an observable startup failure, not permission for JBPA to override customer policy.

## Incident evidence

On 12 October the QA agent upgraded from 12.10.1.1 to 12.11.3.2. The installed vendor `post.sh` removed old expansions and restarted by default. The deployed JBPA upgrade verifier then invoked `NativeLinuxWorkflow.run`, which unconditionally restarted again. Axis was left with 118 missing libraries and a truncated `joda-time` JAR. A subsequent startup rejected it with `zip END header not found`, while JBPA recorded `SUCCESS / UPGRADE_COMPLETE` using core/connectivity checks. The double-restart path and false success are confirmed; interruption by the second restart is strongly supported, not independently reproduced. The 14 October manual repair was an explicitly authorized incident action, not the normal upgrade design.

## Downgrade and reinstall

An explicit request to downgrade is supported through the existing complete local uninstall/fresh reinstall workflow. Do not pass an older package into the in-place upgrade command: PostgreSQL data/version compatibility is not qualified for that route. A same-major version number alone does not prove an in-place downgrade is safe.

The remote caller now supports:

```bash
./bin/jbpa-remote reinstall --inventory /private/inventory.json --target qa-vm --version 12.9
```

The on-host reinstall pins and validates the target package before removal, checks host resources, holds the lifecycle lock, drains and uninstalls, verifies a clean host, then performs fresh installation/registration and initial synchronization. Protected registration inputs remain on the VM. Local uninstall removes TranDb/local execution history; retain requested diagnostic evidence first. A fresh agent identity may be created and consume another Harmony slot. Do not delete the old Harmony record automatically. The requested version and canonical host must remain fixed across the sequence; an unknown outcome is reconciled before retrying.

12.9 resolves to 12.9.2.2 in the governed catalogue. The current resource exception is scoped to controlled QA 12.10 on the existing two-vCPU Ubuntu 24.04 VM; it must not silently extend to 12.9. A failing 12.9 preflight blocks removal. Supporting the recovery command is not evidence that a live downgrade or the repaired upgrade path has been qualified.

## Validation

Regression checks cover a vendor-started runtime with no JBPA restart or file writes, slow expansion, permanently incomplete Axis despite running services, same-size corruption, invalid WSDL/error pages and unsafe symlinks. Full uninstall/reinstall and subsequent upgrade remain live qualification activities on an eligible named QA host. The deferred production skill security phase is unchanged.

## Current QA candidate and recovery preflight

The fixed candidate is staged separately under `/opt/jbpa/qa-candidates/upgrade-observer-20261014-v2/jbpa-1.0.0-rc9`; the historical pinned release is not overwritten. The remote caller refuses upgrade on legacy releases lacking the `VENDOR_INSTALLER_OBSERVATION` capability, rather than silently invoking the old restart verifier. Candidate builds are identified by their manifest/digest, not treated as a newly certified production release.

On the current two-vCPU target, the 12.9 reinstall resource preflight failed before removal (minimum four vCPUs). Subsequent secret/network checks were skipped by that prerequisite gate, rather than evidence of broken credentials. A separate direct credential check passed, and the fixed read-only application probe observed all 302 packaged Axis files matching with valid conversion WSDL. The current agent remains 12.11.3.2. Live recovery awaits suitable VM sizing or a specifically authorized version-scoped QA exception; the subsequent upgrade has not been executed.

## Explicit 12.9 QA exception — 2026-10-14

The user explicitly authorized the two-vCPU exception for 12.9 on JBLAB-PA-AUTOMATION. The optional `qa_policy.scoped_cpu_exception` binds hostname, logical version 12.9, exact package 12.9.2.2, CPU count two and explicit-user-approval classification. Both readiness and bootstrap require controlled-test mode, Ubuntu 24.04 amd64 and the exact scope. Production, other hosts and other packages remain blocked. The target uses a separate root-only `/etc/jbpa/qa-reset-12.9-20261014.yaml`; the general agent configuration is not replaced.

For fresh installation, JBPA now waits for the vendor's initial Axis expansion before the supported registration restart. This prevents restarting during extraction; it does not suppress vendor startup or alter package scripts. Upgrades continue to observe only, with no verification restart.

The checked candidate is `/opt/jbpa/qa-candidates/upgrade-observer-20261014-v3/jbpa-1.0.0-rc9`, archive SHA-256 `c9238920fdb71b40e9459fc7185bf29123bb8e0283dd442476877b9d52da4a8a`. All 494 unit tests passed before the live reset. A bounded 25-query TranDb snapshot is retained locally; raw logs remain in a root-only target backup. Live reinstall outcome is recorded separately and does not qualify a subsequent upgrade.

### Live reset outcome

The first reinstall completed package installation but no vendor Tomcat startup was observed. The initial waiting guard correctly failed readiness but incorrectly assumed an expansion was in progress. The guard now waits only for an observed vendor Tomcat process; if services were left stopped, the existing supported fresh-registration/start path proceeds. A regression test covers this case. No vendor autostart policy, scripts, WAR contents or deployment permissions were modified in the fresh reset.

The installed 12.9.2.2 package was resumed from verified unregistered/stopped state without repeating uninstall. Registration succeeded as agent 667590 in PAG 679240; group synchronization completed at 2026-10-14 17:34:00 UTC. Axis had 302 matching packaged files, no missing/mismatched files, and valid conversion WSDL HTTP 200. Connectivity passed. Original and QA-profile expected-health identity metadata were refreshed only after independent identity checks, with private backups. The initial failed result and separate successful recovery evidence are both retained.

Final candidate: `/opt/jbpa/qa-candidates/upgrade-observer-20261014-v4/jbpa-1.0.0-rc9`, archive SHA-256 `f48f0b5aa610ebe048a0241eac2410c93b6af66f7878436e0228682ed5b109d0`; 495 unit tests pass. The older pinned release was not overwritten. No subsequent upgrade or business-operation test has been executed.

## Fixed-path live upgrade — 15 October 2026

The explicitly authorized host/package-scoped two-vCPU QA upgrade from 12.9.2.2 to 12.11.3.2 completed successfully through the normal vendor installer and read-only observer. Axis files/WSDL, fresh authentication/request flow, retained agent identity, services and 15 unchanged operation definitions pass. No verification restart or manual application repair was performed. See [exact validation and evidence](upgrade-12.11.3.2-qa-validation.md) for timing, candidate/package digests, scope and canary limitations. Production qualification remains unchanged.
