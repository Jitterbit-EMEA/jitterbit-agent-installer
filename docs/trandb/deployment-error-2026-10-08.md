# Deployment token-invalidation diagnosis — 8 October 2026

The reported `AGENT_TOKEN_INVALIDATION_ERROR` is backed by a local Tomcat HTTP 404 on the `/axis` application. Startup logs show `/axis` failed to initialize because required Java classes were unavailable. Its expanded library directory has 161 JARs; the installed `axis.war` has 256, with 95 missing from the expanded application and no unexpected libraries. This is strong evidence of an incomplete application expansion, rather than a general inability to reach Harmony.

The source of the incomplete expansion is not established. No restart, directory replacement, credential change, re-registration, package repair or deployment retry was performed during diagnosis.

## Confirmed observations

| Check | Result |
| --- | --- |
| Target / PA | JBLAB-PA-AUTOMATION / 12.11.3.1 |
| Agent / group | 665400 / 678370 |
| Core services | Running |
| Harmony, Apache and Tomcat reachability | Connection check passed |
| Full independently qualified health | Not established by this status command |
| Clock | Etc/UTC; NTP synchronized |
| Available disk | Approximately 56.8 GB |
| Active locally retained operations | 0 |
| Token-invalidation request | Local HTTP to 127.0.0.1:46912, context `/axis`, response 404 |
| Token-invalidation observations | Repeated at 17:44:54, 17:45:31, 17:45:42, 17:47:24 and 17:47:28 UTC |
| Axis startup failure | Recorded at approximately 12:42:31 UTC |
| Axis libraries | 256 packaged; 161 expanded; 95 missing |
| Other application comparison | jitterbit-agent WAR and expanded libraries both contain 216 JARs |

Missing-class errors include Spring `ContextLoaderListener`, Jitterbit `ApplicationServletContextListener`, `ConnectorContextServletListener` and `ServerConfig`. Library-count equality alone is not a content-integrity check; the missing-name comparison independently confirms the Axis discrepancy.

The installed Axis WAR passed a complete ZIP CRC check and its SHA-256 was recorded in `output/trandb/deployment-error-war-integrity-2026-10-08.json`. This establishes archive readability/integrity, not independent vendor provenance.

## Proposed repair, not executed

1. Confirm that no operations or deployments are in flight; capture current health and workload state.
2. Verify the installed `axis.war` archive is readable and intact, and record its digest.
3. Stop the agent services for a controlled maintenance interval.
4. Move only the expanded `tomcat/webapps/axis` application into a protected backup outside Tomcat's webapps directory. Preserve `axis.war`, agent configuration, credentials and PostgreSQL data.
5. Start the agent and allow Tomcat to re-expand Axis from the installed WAR.
6. Verify expected library names/content, successful Axis startup, core services, Harmony connectivity and unchanged agent identity.
7. Retry the customer deployment to establish that invalidation and project synchronization now work. Runtime health alone does not prove the deployment error is resolved.

This needs a short service interruption. A rollback restores the backed-up expanded application while services are stopped if the repaired application fails to initialize. Do not automatically reinstall or re-register the agent. The actual repair must stop on evidence of a corrupt source WAR or unexpected in-flight work.

## Evidence and repeatability

- `output/trandb/deployment-error-details-2026-10-08.json`: exception classes and HTTP status observations.
- `output/trandb/deployment-error-endpoint-origins-2026-10-08.json`: local request origin, with paths/query values withheld.
- `output/trandb/deployment-error-startup-details-2026-10-08.json`: startup context and missing-class evidence.
- `output/trandb/deployment-error-context-check-2026-10-08.json`: context correlation and library counts.
- `output/trandb/deployment-error-library-diff-2026-10-08.json`: the 95 missing library filenames.
- `output/trandb/workloads/after-project-2026-10-08-01/`: final read-only TranDb capture; 163 profile and 25 reporting queries succeeded.
- `scripts/management/inspect-agent-deployment.py`: repeatable bounded on-host log classifier. Requires protected SSH staging like the TranDb capture scripts; no raw messages or credentials exported.
- On-VM status result: `/var/lib/jbpa/results/remote-status-69fc2d7918354bb8a1e7f0bfb6aacc93.json`.

## Product learning

A service process and open local port do not establish application readiness. Management health should include an Axis startup/application check, WAR-expansion integrity evidence, and a separate deployment verification result. Preserve `HTTP 404`, endpoint component and context failure as distinct diagnostic facts instead of collapsing them into a generic credentials error.

The public [Harmony troubleshooting guide](https://docs.jitterbit.com/getting-started/troubleshooting/) recommends agent logs and support-tool diagnostics, and notes that restarting terminates operations in progress. No public remedy for this exact token-invalidation code was located during this investigation; the diagnosis above comes from the live host evidence.

## Approved repair outcome

The user approved the repair. It completed at 18:02:42 UTC on 8 October 2026. Preflight found zero active runs and zero incoming requests. Services stopped and restarted successfully; the original Axis expansion was preserved at `/var/lib/jbpa/backups/axis-20261008T180113Z-6a8be28b`.

Tomcat logged fresh Axis deployment completion at 18:02:12 UTC. All 256 library JARs are present and match their WAR size/CRC values. The local `/axis/` response is HTTP 200. Agent ID 665400/group 678370 and protected configuration/credential file contents are unchanged. Post-repair diagnostics confirm core services and Harmony connectivity. This is not a claim of independently qualified production health.

Evidence: `output/trandb/axis-repair-completed-2026-10-08.json`, `axis-repair-status-2026-10-08.json` and `axis-repair-startup-2026-10-08.json` in the same output directory. The initial attempt aborted before any service changes because the optional installer credentials JSON was absent; the corrected check preserves absence as well as the actual registered-agent credential file.

**Remaining validation:** Retry the customer project deployment. Until that succeeds, the result remains `REPAIRED_PENDING_DEPLOYMENT_RETRY`; local Axis readiness does not alone prove Harmony's invalidation request succeeded. Keep the protected backup until deployment has been validated.

## Deployment retry and requested version change

The customer retried deployment and reported the same token-invalidation error. Therefore the application expansion repair did not establish end-to-end resolution. The customer explicitly requested uninstalling the agent and installing v12.10. Complete local uninstall succeeded; the existing protected registration settings remain outside the removed agent directory. Reinstallation progress is recorded separately. The old Harmony agent record was not deleted automatically.

## v12.10 installation completed

Complete uninstall and fresh installation succeeded. Installed build: 12.10.1.1; newly registered agent ID: 665430; group: 678370. Registration/service checks, subsequent Harmony connectivity, Axis HTTP 200 and all 256 expected Axis libraries passed. The old record 665400 was not deleted from Harmony. A new TranDb baseline was captured under `output/trandb/workloads/fresh-1210-2026-10-08/`. Retry project deployment to determine whether the original token-invalidation error is resolved on this version.
