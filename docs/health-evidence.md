# Registration and health evidence model

Historical Phase 1.5 design, references accessed 2026-09-22. Later native registration and lifecycle evidence supersede the original no-live-evidence assessment. The current Phase 2F.1A existing-agent restart rules and Support Tools provider are in [the lifecycle health contract](health-contract.md); the historical design below is retained for traceability.

## Signals and meaning

| Signal | Evidence | Proposed gate | Limits |
| --- | --- | --- | --- |
| Installed package/build/architecture | D01; future package database query plus approved digest | Mandatory | Does not prove any service or Harmony registration |
| Local core service state | J03 `jitterbit status`: Process Engine, Scheduler, Cleanup | Mandatory | Return-code semantics not documented; host-only |
| Supporting service state | J18 tools: Apache, Tomcat, PostgreSQL, PgBouncer, VerboseLogShipper | Mandatory for components required by qualified profile | Not the same service set as jitterbit status |
| Product credentials metadata | J04 creation/persistence | Mandatory for fresh registration; preserved evidence on rerun | Existing file can be stale, copied, or for another identity; no contents collected |
| Connectivity | J18 connection-check | Recommended diagnostic; transport validation mandatory via a qualified probe | Gateway/Apache/Tomcat reachability does not prove TLS/authentication/group membership/heartbeat or workload success |
| Current attempt logs | J11 main and installer logs | Known fatal registration failures veto success; unknown/absent evidence cannot create success | Human strings require exact-build fixtures and context |
| Current Harmony identity and Running | J12/J19 | Mandatory for full COMPLETE under existing require_cloud_confirmation=true | Operator verification is allowed test evidence, not an automated API |
| Test integration operation | Future dedicated operation | Recommended qualification; production acceptance separately | Registration is not end-to-end business processing |

## Agent Support Tools: verified interface

J18 documents launching `/opt/jitterbit/AgentSupportTools/run.sh` from its directory, then issuing commands at the interactive tool prompt:

```text
service-status
connection-check [-t]
generate-report
```

`-t` adds traceroute when installed. The first two commands have no documented JSON option or stable OS exit-code contract. Other commands such as apache-stat support JSON; do not generalize that support. In particular, `run.sh service-status` is **not verified syntax**. Need installed launcher/help inspection before building a noninteractive adapter. A launcher exit of zero must not mask a failing inner command. Prefer reliable exit/status data when proven; otherwise use tightly scoped versioned fixtures, not broad human-text scraping.

`generate-report` creates HTML and a log archive; Linux currently omits PostgreSQL information due to a documented connection problem (J18). It is diagnostic only, never a health gate. Bulk archives can include sensitive data and are excluded from routine automated collection until reviewed/redacted.

## Log classification inventory

Only newly appended, relevant log records associated with this run/identity may count. Capture inode/offset and start time; handle rotation/truncation. Existing log success is not current evidence.

| Class | Public evidence and disposition |
| --- | --- |
| SUCCESS | J01 documents an environment/group synchronization completion message in upgrade context. It is not a universal registration-success string. No exact universal marker established |
| AUTH_FAILURE | No stable Harmony-registration marker established. Do not classify bundled PostgreSQL login errors as Harmony auth failures |
| NETWORK_FAILURE | J12 documents `java.net.SocketTimeoutException: Read timed out`; use as contextual diagnostic, not universal registration RCA |
| TLS_FAILURE | J12 discusses certificate/handshake failures; exact native 12.10 registration matcher needs a captured fixture |
| PROXY_FAILURE | J08/J12 describe setup/proxy faults; no qualified registration-specific exact matcher |
| REGISTRATION_FAILURE | J12 describes stale identity after deregistration; exact build-specific signal still required |
| UNKNOWN | Everything unqualified; sanitized reason and evidence reference; never success by default |

A log parser must distinguish target endpoint errors from Harmony errors and initialization noise from terminal registration errors. Do not use absence of errors as proof of health. No parser or fixture is invented in Phase 1.5.

## Control-plane investigation

J19 documents Console agent statuses. J20 Console AI can report agent status but is a natural-language UI capability, not a supported programmatic contract. J21 Citizen Integrator documentation contains an Agent data model with a status field; this alone does not establish a current supported list/get endpoint, authentication scope, freshness or semantic mapping for this use. J22's documented local listening-service REST endpoints concern cluster/listener state, not authoritative Harmony Running status. J05's Agent Registration token is not documented as a general Management Console read token. J03 utilities and J18 support commands do not establish that cloud read contract either.

**No supported, current machine-readable mechanism equivalent to Console Running was established by this research.** This is not a claim that none exists. Ask Jitterbit for a supported API/CLI specification and read-only auth requirements. No private-API reverse engineering, Console scraping or speculative endpoint calls.

For Phase 2 tests, an authorized operator records UTC time, exact agent ID/group/environment and Console state in sanitized evidence. Keep machine result cloud status unknown until a qualified provider exists; external manual acceptance must be labeled manual. Do not silently weaken the existing schema's cloud-confirmation requirement to produce exit 0.

## Composite gate and timeout (design)

Full gate: approved installed build AND required services healthy AND valid identity lifecycle evidence AND qualified current connectivity AND no current qualified fatal failure AND current authoritative Harmony Running for the intended identity. Local-only evidence produces an unconfirmed outcome, never COMPLETE.

Proposed timing: monotonic registration deadline 300 seconds, poll interval 5 seconds, separately bounded per-probe timeout (initial proposal 10 seconds, capped at remaining deadline). Preserve current schema limits: registration 1–3600, interval 1–60; enforce interval <= deadline. Vendor auto-register retry proposal 10 with 5-second interval, within documented J04 ranges (count 0–300; interval 5–600). Adapter rejects a configured retry budget that cannot fit the outer deadline plus probe/cleanup allowance. No external fresh registration retries by default; poll/retry never deletes identity or creates duplicate agents.

Start deadline immediately before service start/registration submission, so startup time counts. Permanent auth/identity/config errors stop early; a known transient transport failure may be rechecked within the deadline. At timeout stop the newly initiated attempt before cleaning input; otherwise the agent might register after the wrapper reports failure. A previously running reconciled service is preserved. Unknown health returns HEALTH_CHECK_FAILED with reason HARMONY_STATUS_UNCONFIRMED when cloud confirmation is the only missing gate; registration never confirmed by deadline returns REGISTRATION_TIMEOUT. Preserve last successful stage and unknown values. No infinite wait or unchecked subprocess.
