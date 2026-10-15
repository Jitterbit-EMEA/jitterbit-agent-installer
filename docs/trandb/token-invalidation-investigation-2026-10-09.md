# Deployment token-invalidation investigation — updated 12 October 2026

**Resolved — customer confirmed 12 October 2026.** After updating connectors and testing the saved Gmail connection, the customer could deploy. Fresh agent logs show Gmail downloaded and loaded at **09:28:25 UTC**. The working recovery sequence was **Update connectors → test Gmail connection → deploy**.

Before recovery, Axis could not resolve Gmail endpoint entity **37201** in its connector registry and returned HTTP 200 with `status:false`. Core health and registration had passed. The earlier file-lock exceptions are associated load-window evidence; they do not establish the sole underlying cause. The sequence does not isolate the contribution of the update from connection testing.

The sections below retain the historical investigation and evidence at each stage.

## Correlation details

| Field | Value |
| --- | --- |
| Harmony region | EMEA West |
| Organization | 410469 — Jitterbit (SA) |
| Environment | 570050 — 12-Automated Infrastructure |
| Group | 678370 — 7-Automated Infrastructure |
| Current agent | 665430 — Running — 12.10.1.1 |
| Project | Customer \| Jeld Wen - File Persona |
| Studio project GUID | 1a470bd8-5bb7-489b-92d8-400e867d5ab7 |
| Latest correlated Studio error | 9 October 2026, 09:01:48.232 UTC / 11:01:48.232 SAST |
| Error | Failed to deploy — HttpErrorResponse: There was an error in token invalidation for agent [AGENT_TOKEN_INVALIDATION_ERROR] |

## Observed local requests

Tomcat access logs show PUT requests to the Axis token-related endpoint with HTTP **200** at:

- 08:54:41 UTC
- 08:58:40 UTC
- 09:00:09 UTC
- 09:01:48 UTC

Agent Services logged receipt immediately before these requests. No current HTTP 404 token-invalidation exception was captured. The last local response is contemporaneous with the displayed Studio error. Access status 200 proves HTTP-level success, not successful business processing or acknowledgement validation: response bodies were not logged/exported by these probes.

The authenticated Harmony Management Console group details list a single agent, 665430, Running. Agent 665400 is not listed in this group view. This supersedes the earlier expectation that the retained old record might explain the current group failure. No Harmony records were deleted by the assistant.

## What was already tested

The previous v12.11 installation had an incomplete Axis expansion and local invalidation HTTP 404. Re-expanding Axis restored all 256 expected library JARs and local Axis HTTP 200, but customer deployment still failed. The customer then requested complete uninstall and fresh v12.10 installation. Registration, services, Harmony connectivity, Axis readiness and expected library counts passed on v12.10; today's actual invalidation requests now return HTTP 200.

These results do not justify another blind reinstall or credential rotation. They also do not prove the remaining defect is exclusively cloud-side: the local response body or returned acknowledgement could still be invalid.

## Next trace required

Correlate the Harmony deployment request at **09:01:48 UTC** for organization **410469**, environment **570050**, group **678370**, agent **665430**. Inspect:

1. The Agent Services token-invalidation message and response correlation IDs.
2. The local endpoint response body, redacted to remove token and credential values.
3. The response/acknowledgement sent back to Harmony and the expected response schema/status.
4. The backend error that becomes `AGENT_TOKEN_INVALIDATION_ERROR`, including timeout, missing acknowledgement, response validation or returned application failure.

The generic Studio console message does not contain that backend detail. No production project was redeployed by the assistant during this investigation, and no service/configuration/credential changes were made today. The report is ready for a Jitterbit backend/support investigation; it has not been sent to anyone.

## Evidence

- `output/trandb/token-invalidation-findings-2026-10-09.json`
- `output/trandb/deployment-error-1210-2026-10-09.json`
- `output/trandb/token-events-1210-2026-10-09.json`
- `output/trandb/invalidation-access-1210-2026-10-09.json`
- Authenticated Studio console and Management Console group-details observations, recorded above.

The project knowledge catalogue preserves these findings and their limits. Read-only captures can be repeated using the existing workflow; the additional local classifiers export indicators and HTTP codes rather than raw token-bearing messages.

## Proxy hypothesis checked — 11 October 2026

The customer supplied a Jitterbit AI description of a similar 3LO token-invalidation failure on agent 12.2, with local PUT HTTP 503 caused or suspected to be caused by proxy routing. That account is a hypothesis for this installation, not a verified diagnosis or an instruction to change configuration.

The live v12.10.1.1 host was checked read-only:

- The vendor utility `jitterbit-utils --print-http-proxy-configuration` explicitly reports that HTTP proxy is not enabled. Its output was filtered on the VM; proxy credential values were not exported.
- Both Java processes have no allowlisted proxy-host overrides in startup arguments/JAVA_OPTS, and no HTTP/HTTPS/ALL_PROXY server variables were found in their environments.
- Both have `no_proxy=localhost,127.0.0.1`.
- No proxy-related fields were present in the loaded `jitterbit.conf`; the inspected launch files contained no allowlisted proxy assignments.
- Neither bundled nor system `jcmd` was available, so runtime-set JVM system properties were not directly inspected.

The four actual local invalidation PUT responses captured on 9 October were HTTP 200, rather than the HTTP 503 described in the supplied account. Thus the checked configuration and request evidence do not currently support proxy misrouting as the cause here. A logical failure in an HTTP 200 body or in acknowledgement/response validation remains possible and unresolved.

Java's standard networking proxy properties use `http.nonProxyHosts` with vertical-bar-separated patterns; HTTPS uses the same property. Shell `no_proxy` is a separate setting and its presence alone does not prove a particular Java HTTP client honors it. See [Oracle networking properties](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/net/doc-files/net-properties.html) and [Jitterbit's proxy configuration guidance](https://docs.jitterbit.com/agent/proxy/). No proxy change, downgrade or restart was made during this check.

Evidence: `output/trandb/proxy-investigation-2026-10-11.json`, `proxy-config-fields-2026-10-11.json` and `vendor-proxy-configuration-2026-10-11.json` in that directory. The reusable non-secret JVM/config/environment collector is `scripts/management/inspect-agent-proxy.py`.

## New PAG and response-body evidence — 11 October 2026

The customer deleted the previous PAG/environment and created PAG **679240**. Agent **667310**, v12.10.1.1, registered successfully after the customer provided a newly generated registration token. Configured steady-state health passed. The new environment is **571300**; 10 operation definitions synchronized locally, with zero retained executions in the capture.

Deployment still failed. A narrowly scoped passive loopback capture at **19:37:57 UTC** observed the actual PUT response from `/axis/v1/token/3lo/invalidate`:

```json
{"httpStatus":200,"bodyBytes":202,"chunked":true,"jsonBody":true,"safeResponse":{"status":false,"errorCode":null}}
```

This is an explicit application failure carried inside HTTP 200. It supersedes the earlier assumption that transport success left only an acknowledgement gap. The handler's error field must be inspected to explain why it returned false. The first capture exported only allowlisted status fields; raw response bytes, token values and headers were not persisted. The Axis and component-listener log probes returned no matching exception records, so a second bounded filtered response capture was prepared.

Evidence: `output/trandb/invalidation-response-new-pag-2026-10-11.json`, `axis-invalidation-errors-new-pag-2026-10-11.json`, and `output/trandb/workloads/new-pag-deploy-error-2026-10-11/`. The latter completed 157 profiling and 25 reporting queries with no unavailable queries. The passive helper is `scripts/management/capture-invalidation-response.py`; it opens no listening port and changes no service/configuration. It retains only loopback invalidation response status and allowlisted structural/technical indicators.

## Gmail registry failure isolated

A synchronized deployment captured a request with one connector GUID and environment ID 571300. The response contained `status:false`, null operation/error fields, and empty successful/failed/not-found GUID lists. The controller was therefore not reporting outcomes for the requested connector.

Whitelisted TranDb lookup maps entity **37201** to **gmail / Gmail Endpoint**, environment **571300**, `is_global=false`. Axis logs repeatedly record the controller unable to find the connector for that entity. The connector-load window contains `java.nio.channels.OverlappingFileLockException` and a retry exception. Compiled controller method/type metadata confirms the registry lookup and dispatch to `JitterbitConnectorAdapter.performTokenInvalidation`; no vendor code was patched.

The proposed next repair is the documented **Update connectors** action for only PAG **679240**, followed by checks that Gmail loads and deployment succeeds. Active operation count was zero. The action is prepared on Harmony's “Are you sure you want to update connectors…” dialog. It has **not been confirmed or executed**. Browser interaction policy requires explicit approval to accept that confirmation when the specific update action was not explicitly requested. The screenshot is `output/trandb/connector-update-confirmation-2026-10-11.jpg`.

[Jitterbit's connector troubleshooting guide](https://docs.jitterbit.com/integration-studio/troubleshooting/connector/) documents connection testing and the agent-group Update connectors action as supported ways to obtain current connector packages. This action overrides the Disable Auto Connector Update policy for that group. It is a proposed connector recovery, not another PA reinstall.

Evidence: `output/trandb/invalidation-request-response-2026-10-11.json`, `token-controller-registry-log-2026-10-11.json`, `connector37201-load-error-2026-10-11.json`, and `token-controller-references-2026-10-11.json`. All temporary packet observers were bounded and finished; staged scripts were removed. Raw request/response headers, token values and messages were not persisted. The assistant performed synchronized retries of the existing saved project without editing its components; the same deployment failure was reproduced.

## Recovery confirmed — 12 October 2026

The customer performed the connector update and tested the saved Gmail connection. Filtered live logs show Gmail downloading from **09:27:34 UTC**, followed by a Gmail `ConnectorLoader` loaded event at **09:28:25 UTC**. The customer then confirmed: “After testing the gmail connector, I can deploy”. No additional reinstall or service change was performed for this recovery check.

Deployment success is customer-confirmed. A post-recovery invalidation response body was not captured, so this report does not claim a directly observed `status:true` response. Evidence: `output/trandb/gmail-deployment-recovery-2026-10-12.json`.

**Build requirement:** distinguish connector package download, runtime load and registry availability from general agent health. Check the affected connector before declaring deployment readiness, and inspect application status rather than accepting HTTP 200 alone. The supported recovery sequence is catalogued as a reusable runbook in `knowledge-catalogue.json`; automated remediation has not been implemented.
