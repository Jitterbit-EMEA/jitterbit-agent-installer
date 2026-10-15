# JBPA Management product specification

Status: proposed product baseline, 2026-10-05. This specification is not an implemented or production-qualified service.

## Objective and customer boundary

Deliver one versioned, customer-deployable management stack for Linux container hosts, plus a matching Jitterbit integration kit. Each customer operates an independent installation. Target hosts remain pre-provisioned; the existing JBPA runtime owns agent lifecycle actions. No additional listening services are installed on target PA hosts.

The first supported management deployment is Docker Engine with Compose on a dedicated Linux host. Exact distribution, architecture, runtime versions, resource sizing and target compatibility must be published after qualification. Container portability does not imply support for every Linux host or every target platform.

## Delivery sequencing and deferred upgrade

Skill security decision, 2026-10-13: the immediate concern is the JBPA skill through Codex/Claude, not the MCP solution. The [skill access architecture](skill-security-architecture.md) records SEC-SKL-001 through SEC-SKL-014 as the **final selected implementation phase**, started only when the user explicitly asks. Production monitoring must be read-only, with separate authenticated approval and execution for install, upgrade, uninstall and deregistration. This documentation update does not change the skill, caller or infrastructure. Deferral does not authorize production access before these controls are implemented and qualified. The [roadmap](jbpa-management-roadmap.json) records this gate separately from MCP upgrades.

Decision recorded 2026-10-07: establish and validate the management baseline first. PA/host observability is a subsequent product upgrade, not a baseline acceptance dependency. Approval of this roadmap does not authorize installing monitoring components or running the upgrade now.

The baseline retains the lifecycle caller, permitted target listing, synchronous getVersions catalogue discovery, basic status/health/installed-version actions, durable job submission and retrieval, API/worker persistence, database-backed job execution, canonical-host ownership and recovery. Existing health checks and the TranDb active-operation check required for safe draining remain in the baseline. Broad operation-history APIs, detailed host/component metrics and continuous collection are deferred.

**UPG-001 - PA and host observability:** `DEFERRED_UNTIL_BASELINE_VALIDATED`. Scope includes deployed operation inventory; running/pending/terminal execution history and details; operation summaries; PA service and database health; Apache, Tomcat, JVM and Jitterbit runtime metrics; host/process metrics; connectivity diagnostics; bounded redacted logs; capability discovery and timestamped metric snapshots. The machine-readable [upgrade roadmap](jbpa-management-roadmap.json) records the proposed tools, boundaries and release gates.

Begin the upgrade only after the baseline has demonstrated clean deployment, authenticated MCP discovery/calls, end-to-end APIM/Studio submission and database-backed execution, correct target execution and result retrieval, duplicate suppression, same-host serialization, interrupted-execution reconciliation and backup/restore. Upgrade rollout remains an explicitly scheduled release activity following qualification.

The upgrade preserves the dedicated management host and existing SSH transport. No additional persistent service or listening port is introduced on target PA hosts. Detailed JVM/Tomcat metrics remain capability-dependent; missing instrumentation is reported as unavailable. Agent TranDb stays distinct from the management PostgreSQL job database. Version-qualified, bounded read-only queries expose named data contracts; arbitrary SQL and shell execution are not tools. Operation definitions, execution records and management lifecycle jobs are separate identities and datasets.

## MCP driven customer onboarding

Current decision, 2026-10-07: Jitterbit MCP drives target configuration, file selection/transfer, validation and remote PA installation. The AI does not run an interactive management installer or require management-host shell access. The customer first runs the management installer locally on the bare management VM to deploy and verify API/worker/database/HTTPS. Jitterbit APIM/Studio/MCP is configured only after those services are running. It does not require all target configuration to be completed first. The [requirements matrix](jbpa-management-requirements-matrix.md) records this correction and retains stable IDs for previous discussions.

### Customer journey

1. The customer runs the management installer on the bare dedicated VM. It resolves every required runtime parameter from validated input, protected secret references or declared generated defaults, deploys the stack and reports management readiness. There is no management API, worker or MCP-driven bootstrap before this completes.
2. Configure the Jitterbit project/APIM/MCP connection to the running management API and verify tool connectivity. Target onboarding follows through MCP. Pre-provisioned target hosts remain required.
3. Call getSetupGuide. Return a setup session identifier, product-owned versioned Markdown guide and aligned machine-readable schema/questions. The AI uses the guide to ask how many hosts are required and collect missing non-secret choices.
4. Call getSetupOptions. List authorized groups/profiles and typed file candidates already staged or uploaded. The customer explicitly maps keys, known-host records, registration profiles, certificates and optional features to each host. Support common defaults with per-host overrides and additional hosts later.
5. For missing files, use the authenticated Jitterbit file-transfer endpoint. A capable client/upload helper or private upload page sends bytes through APIM/Studio to protected management storage. Return file/profile IDs and safe metadata to the AI. Markdown cannot make a client read local files, and private key contents are not passed through the model as tool arguments.
6. Call saveSetup with structured answers and file/profile references, then validateSetup. Backend schema, authorization, ownership/access checks, qualification and current profile/file revisions are authoritative; Markdown cannot bypass them. Display the plan and per-host readiness. Credential structure/connectivity is distinct from verified Harmony registration.
7. Call executeSetup for the approved plan revision and idempotency key. Persist per-host jobs; the worker securely creates/transfers target-specific credentials/configuration, obtains the pinned JBPA bundle and invokes the fixed remote installer through existing SSH. Do not introduce new target listeners or copy management login private keys to the PA host.
8. Retrieve getSetupStatus/getJob results and real registration/package/service evidence. Resume incomplete sessions and reconcile unknown execution outcomes before retry. Switching the active authorized group changes future context, not existing PA registration or already accepted jobs.

### Management installer parameter completeness

The management VM is initially bare. The customer runs the installer locally; it does not call management services that do not exist yet. Every required runtime field has a declared source, validation rule and consumer. Generated secrets/defaults do not require unnecessary customer questions. Missing required values stop the applicable stage rather than producing a partially configured service presented as ready.

| Parameter group | Source and required behavior | Consumer |
| --- | --- | --- |
| Deployment identity and supported platform | Installer creates a deployment ID and checks the selected supported Linux/container runtime; exact supported tuple remains qualification-gated | All services and release manifest |
| Management address and HTTPS | Customer selects reachable hostname/IP and certificate/gateway profile; installer validates key/certificate/chain and generates routing | NGINX and Studio connection setup |
| API authentication and permissions | Customer supplies the selected identity-provider policy and machine credential references; installer validates required issuer/audience/trust and role/action scope configuration | FastAPI; later Studio authenticated calls |
| Database identity and connection | Installer generates protected local application credentials or validates a selected external DB profile; database name, role and private connection settings are resolved | PostgreSQL, API, migrations and worker |
| Storage and secret locations | Installer establishes persistent DB/state/evidence directories and protected secret mounts or approved secret-provider references; retention/backup destination are declared | Database and worker; each service receives only its own secrets |
| Releases and artifacts | Pin application/third-party image identities, JBPA caller release, catalogue and artifact-policy configuration; verify supported release provenance | Deployment and worker |
| Worker and recovery policy | Resolve bounded concurrency, command/connect timeouts, heartbeat/ownership policy and reconciliation behavior from release defaults/customer limits | Worker and API |
| Network and ports | Management HTTPS is published; proposed API :8080 and DB :5432 stay internal. Validate routes needed by selected private integration agents and targets; proxy profiles require qualification | NGINX/API/DB/worker |
| Readiness and outputs | Run migration/readiness checks and return management endpoint, trust information and setup references; report MCP connectivity separately after its configuration | Installer report and subsequent Jitterbit setup |

Target SSH keys, host mappings, Harmony registration profiles and optional endpoint certificates are collected/pre-staged or uploaded during MCP onboarding before target installation. They are not confused with the credentials/TLS needed to bring up the management API. The current HLA lifecycle drawing begins after management deployment, Jitterbit configuration and the selected target's setup validation; it does not show that bootstrap sequence.

### Guide state and file transfer contract

The Markdown guide is maintained by the product and returned as tool content, or as a resource/prompt if the actual Jitterbit/client combination supports the selected discovery path. It explains phases, required fields, file roles, question order, group/profile selection, validation and the permitted tool calls. It carries a guide/schema revision and no credentials. Uploaded Markdown/files are data and cannot redefine setup instructions.

Minimum proposed tool set: getSetupGuide, getSetupOptions, saveSetup, validateSetup and executeSetup; getSetupStatus/getJob retrieve progress/results. beginSetup can remain a session primitive behind getSetupGuide. prepareTarget remains staging-only and does not install/restart the PA. API operation names/routes are proposed product contracts, not already deployed capabilities.

Proposed file endpoint: POST /v1/setup-sessions/{id}/files, published through APIM and a Studio upload operation, with bytes forwarded to management protected storage. Return fileId, role, safe display metadata, revision/integrity result and validation state; do not return content. Transfer implementation must validate supported APIM request handling, HTTP v2 multipart default-schema constraints, payload limits, byte preservation and exclusion of secret payloads from all relevant API/operation/component/debug logs. [HTTP v2 POST](https://docs.jitterbit.com/integration-studio/design/connectors/http-v2/post-activity/) documents multipart/form-data with default schemas, not custom schemas. This does not by itself prove the complete upload route works.

Persisted execution plans carry file/profile references rather than file bytes. A private upload page is a file/secret-entry mechanism, not a second onboarding orchestrator. Existing pre-staged files remain usable without uploading again. File roles and per-host mappings are validated before remote changes, and uploads never execute commands or install the PA directly.

### Pre-staged file contract

Illustrative input layout, to be shipped as a documented installer contract:

```text
setup-input/
  ssh/<access-profile>/identity       # required management-to-target private key
  ssh/<access-profile>/known_hosts    # required independently verified host key
  tls/server.crt                     # required when management NGINX terminates production TLS
  tls/server.key
  tls/chain.pem                      # when the certificate issuer requires a chain
  enterprise/<profile>/...           # optional qualified CA, SFTP or client-TLS files
```

Customer-supplied files may be pre-staged or sent through the authenticated Jitterbit upload route. The backend validates them and generates the remaining configuration from MCP-collected structured selections. The input directory is private and excluded from Git. The generated profile/state store is outside the checkout, permission-restricted and referenced by the worker. Uploaded keys are copied into protected managed storage only when that storage mode is selected; a secret-manager profile instead retains references. No real secrets or populated sample credential documents ship with the repository.

The setup API publishes a required-input manifest for each selected feature, distinguishing required/pre-staged files, prompted fields, generated files, destination/owner/permissions and validation rules. Optional enterprise features remain explicitly unqualified until their existing release gates pass. Missing mandatory input stops that feature before remote changes. Compatibility with a customer's existing TLS gateway or secret manager changes the manifest through a declared profile, not through ad hoc fallback behavior.

The existing `bin/jbpa-customer setup` and `bin/jbpa-install` provide local guided credential capture and setup/install composition for the current QA contract. They are not yet the management-host/MCP onboarding product. The first-release implementation must reuse their credential schema, validation and lifecycle engine while adding durable management-side onboarding and secret delivery.

### Onboarding MCP and API contract

| Tool | Proposed parent API | Responsibility |
| --- | --- | --- |
| getSetupGuide | POST /v1/setup-sessions | Start/resume a scoped session and return its Markdown guide and schema revision; no credential values |
| getSetupOptions | GET /v1/setup-sessions/{id}/options | List authorized groups/profiles and typed staged/uploaded file IDs |
| saveSetup | PUT /v1/setup-sessions/{id}/configuration | Validate and persist structured answers, per-host mappings and plan revision |
| validateSetup | POST /v1/setup-sessions/{id}/validate | Run bounded checks and record readiness; no implicit PA registration or install |
| executeSetup | POST /v1/setup-sessions/{id}/execute | Create durable per-host lifecycle work from the validated plan revision |
| getSetupStatus | GET /v1/setup-sessions/{id} | Return safe stage/check/job results and required next action |
| prepareTarget | POST /v1/targets/{id}/prepare | Stage approved configuration without installing/restarting the PA |

Profile/token capture uses protected secret references or private authenticated input routed to the backend; actual secret values are not ordinary AI-visible arguments or stored in jobs. Target preparation/replacement is permission-scoped and serialized with canonical-host lifecycle work. A corrected profile can resume onboarding without reinstalling the management stack. Initial management bootstrap requires its own deployment identities/TLS/network setup; it is not the AI-assisted installer proposed earlier.

The existing local JBPA setup/install commands remain reusable lifecycle/credential-schema foundations and QA tooling. MCP-driven management onboarding and the Jitterbit upload route remain unimplemented. Acceptance requires completion of a multi-host MCP flow without local AI shell access, safe four-key selection, correct group/profile isolation, upload integrity and logging checks, truthful credential/registration status, durable execution and all original recovery guarantees.

## Deployment components

| Component | Baseline | Responsibility |
| --- | --- | --- |
| HTTPS entry point | NGINX container, or documented customer gateway replacement | TLS termination, request limits, upstream routing |
| Management API | Python, FastAPI, Pydantic, Uvicorn | Authentication, authorization, target discovery, durable job submission, status and dispatch APIs |
| Worker | Separate Python process/container using the same released application image | Claim jobs, execute the pinned JBPA caller, record results and reconcile interruptions |
| Database | PostgreSQL; SQLAlchemy and Alembic proposed for data access/migrations | Authoritative jobs, events, idempotency, execution ownership and audit records |
| Execution adapter | Pinned JBPA remote caller and release | Fixed commands, verified artifacts, pinned SSH host keys, named targets |
| Jitterbit kit | Studio project, APIM endpoints, upload operations and MCP definitions | Submission, file transfer, status and optional completion notifications |

Only the HTTPS entry point publishes a management-host application port. PostgreSQL and application ports remain within container networks. Only the worker receives target SSH identities. All services run without privileged mode or Docker socket mounts. Host-root access is not required to manage remote targets.

NGINX, API and database access are isolated from the worker's SSH credentials. Customer secrets are provisioned separately from release images. Compose secret files are protected host files, not an encrypted secret-management service. A customer secret manager can supply the mounted files.

## Request and execution flow

Current planning direction, 2026-10-08: the baseline uses PostgreSQL as the durable worker backlog. The previously proposed JBMQ/outbox/dispatcher layer is superseded for baseline installation; it added a second delivery path after the job was already durably accepted.

```text
AI -> Jitterbit MCP -> APIM -> Studio -> POST management /v1/jobs
Management API -> PostgreSQL: commit validated READY job; return jobId
Worker -> PostgreSQL: claim READY job and canonical-host ownership
Worker -> existing SSH -> target JBPA installer
Worker -> PostgreSQL: persist outcome and evidence
AI -> MCP -> APIM -> Studio -> GET management /v1/jobs/{jobId}
```

The API commits the approved job as READY before returning 202 Accepted. The worker consumes the persisted backlog independently; no install HTTP call stays open. There is no baseline outboxId, queue publication confirmation, dispatch endpoint, Studio queue dispatcher or queue ACK. Idempotency, authorization, exact target/profile/release revisions, host ownership, attempt evidence and reconciliation remain required.

A lost submission response is recovered by retrying the same idempotency identity, not by creating a fresh mutation. Unknown job IDs return not-found. The worker does not blindly replay an uncertain remote outcome. Status calls retrieve current retained job state. Client polling is optional; the user can request the result later.

JBMQ can be reconsidered if a separate durable intake/routing requirement exists, such as accepting requests while the management API is unavailable. That would require a separately defined acceptance contract and qualification; it is not a dependency of the observability upgrade merely because data volume is large.

## Durable data and state

Proposed tables: jobs, job_events, target_execution_ownership, audit_events and schema_migrations. Inventory may remain a validated private configuration file for the first release; each job records its target configuration revision and canonical host identity without storing secret values.

Required job fields include customer deployment identity, caller identity, job ID, idempotency key, canonical request hash, target ID, canonical host ID, inventory revision, action, requested/resolved artifact identity, timestamps, state, execution attempt ID, worker identity, sanitized result and restricted evidence reference.

Baseline states: READY, RUNNING, SUCCEEDED, FAILED, NEEDS_RECONCILIATION. READY is a durably accepted worker-backlog job. The older ACCEPTED_PENDING_DISPATCH state belongs to the superseded queue design.

Idempotency is scoped to caller/deployment and binds the canonical request. A reused key with changed parameters returns a conflict. Repeated submissions and worker recovery must not repeat lifecycle mutations.

Workers use short database transactions to claim work. They do not hold a transaction open during SSH execution. Execution ownership is per canonical host, so aliases cannot bypass serialization. Worker leases and heartbeats detect abandonment, but lease expiry alone never authorizes another mutation while a remote execution may remain active. Host locks remain a second protection.

## Recovery requirements

Before mutation, record a stable execution attempt identity and expected remote evidence location. Extend the existing SSH caller to make remote execution and result discovery recoverable after transport loss. No daemon or additional listening port is required on targets; file/process evidence may be used through existing SSH access.

A timed-out SSH call, worker crash or lost database connection may leave a remote action running. Such jobs retain target ownership and enter reconciliation. Observe remote state/evidence before declaring failure, releasing ownership or starting another action. No automatic reinstall, registration retry loop, Harmony record deletion or blind mutation replay is introduced.

Database restoration must fence workers, reconcile remote executions, and only then resume worker claims. Restored job/profile references must be checked before execution resumes. Downgrading application images is permitted only where database schema and in-flight job compatibility have been verified; generic downgrade rollback is not promised.

## API and access contract

Version APIs under /v1. Proposed routes: POST /jobs, GET /jobs/{id}, GET /targets, GET /versions; setup/session/file-transfer routes are defined above. Separate liveness/readiness endpoints from authenticated business endpoints.

### Baseline getVersions API and MCP tool

`getVersions` is a baseline read-only MCP tool backed by `GET /v1/versions` through APIM/Studio and the parent API. It discovers available PA releases before installation or upgrade. It is distinct from reading the version currently installed on a host.

Optional query inputs: `target` (a permitted inventory target ID) and `action` (`install` or `upgrade`). Without a target, return the governed release catalogue and qualification metadata. With a target, evaluate known OS/architecture and action compatibility; unknown or stale target context must leave eligibility explicitly unverified. Never report an upgrade as eligible from unverified installed-version information.

Return logical version, exact package version, platform/architecture support, qualification, artifact approval state, SHA-256 digest, policy-approved recommendation where available, and target/action eligibility with blocking reasons. Include catalogue revision and response timestamp; identify the source/freshness of any target context. Exclude credentials and protected download URLs. The recommendation may be absent if no release satisfies policy.

Reuse the existing version catalogue, support matrix and JBPA versions provider. This is a short synchronous read: no lifecycle job, JBMQ publication, package download, installation, or mandatory SSH call is required for catalogue discovery. If fresh host observation is needed, use the existing status/job flow and repeat getVersions with that verified context. Job submission independently revalidates eligibility, qualification and approved artifact identity; listing a version does not authorize installing it.

Acceptance: discover and invoke getVersions through Jitterbit MCP; verify catalogue-only and permitted-target results, platform/action filtering, blocked and unverified eligibility, recommendation absence, access denial and catalogue failure. This API remains a proposed contract until the management service and APIM/MCP integration are implemented and exercised.

Validate bearer access tokens against a configured issuer, audience, expiry and signing keys. Provide a documented machine-to-machine authentication integration for Studio and an administrative identity path. Exact IdP and Jitterbit token-acquisition compatibility require integration validation.

Enforce action/target permissions in the management service even when the request passes through APIM. Any delegated end-user identity must be integrity-protected; unverified headers do not establish user authorization. A shared service identity grants only its configured permissions.

Install/upgrade select exact qualified versions and digests. The production execution profile must not inherit RC9 controlled-test overrides. Unsupported actions/platforms and missing artifact approval fail before execution. Cancellation of an executing lifecycle action is not exposed until safe behavior is qualified.

## Release package and customer experience

Ship immutable API/worker images, pinned third-party image identities, dependency lock files, SBOM, provenance/signature verification instructions, Compose manifests, migration tooling, configuration schemas and sanitized examples.

Ship a tested Jitterbit Studio export plus APIM/MCP configuration artifacts where the product supports export/import. Where automation is unavailable, provide exact setup steps and a compatibility checklist; do not fabricate a vendor export format or promise full one-command Harmony setup. Include API/tool contracts, endpoint variables, authentication setup and a smoke-test workflow.

The customer supplies a dedicated Linux host, container runtime, DNS/TLS, private network routes, Harmony entitlements, IdP configuration, backup destination, named target inventory and secret references. Deployment validates prerequisites, verifies release identities, creates persistent storage, migrates the database, starts services and runs non-mutating smoke checks.

Document install, verify, add-target, rotate-credentials, upgrade, backup, restore and diagnostic procedures. Configuration uses references to secret files; secrets are never embedded in example inventory, images, job payloads or AI prompts. A readiness report states separately whether management infrastructure, Harmony integration and target access were verified.

## Availability and operations

The baseline is a recoverable single management host. Compose restart policies do not provide host-level high availability. PostgreSQL data and audit/evidence references require encrypted backups outside the management host and tested restoration. State explicit RPO/RTO after recovery qualification. Offer an external PostgreSQL configuration for customers with an existing managed database.

Use structured redacted logs with job/attempt correlation, READY-backlog and oldest-job metrics, worker heartbeat, reconciliation count, execution duration, database health, disk capacity and backup age. Provide integration with customer monitoring rather than making a second monitoring platform mandatory.

A future HA profile can use redundant API/worker hosts and an HA PostgreSQL service, but must pass split-brain, ownership/fencing and recovery tests before support is claimed.

## Qualification and acceptance

1. Validate clean deployment from a released package on a fresh supported Linux host without source edits.
2. Validate API authorization, target/action restrictions, token/key rotation, secret redaction and network isolation.
3. Test lost submission responses, duplicate submissions, worker claims, retry classification and retained uncertain outcomes.
4. Test multiple workers and same-host aliases; one host mutation must remain the invariant.
5. Test worker/process/host restarts, SSH loss during every mutation phase, remote evidence reconciliation and database outage.
6. Test backup/restore and application/database migration against active and historical jobs.
7. Qualify exact PA/platform tuples and approved upgrade edges on disposable real targets; offline tests cannot replace these results.
8. Run the full Jitterbit MCP/APIM/Studio/management workflow and each supported AI-client result-retrieval experience.
9. Establish management sizing, bounded fleet concurrency, retention and supported dependency/runtime versions.
10. Publish the release support matrix, evidence and remaining limitations before applying the production label.

## Existing evidence boundary

The current repository documents RC9 remote execution as controlled QA on Ubuntu 24.04 amd64, with offline tests and no live remote-caller qualification. Package-changing upgrade is not live-qualified. Artifact production promotion, release supply chain and production sizing remain pending. Product packaging must preserve these limitations until new evidence closes them.

See [current readiness](production-readiness.md), [remote integration contract](integrations/skills/README.md) and [customer qualification notes](customer-start-here.md).

## Primary technology references

- [Docker Compose production deployment](https://docs.docker.com/compose/how-tos/production/)
- [Compose secret-file injection](https://docs.docker.com/compose/how-tos/use-secrets/)
- [PostgreSQL concurrency and locking](https://www.postgresql.org/docs/current/explicit-locking.html)
- [PostgreSQL backup and restore](https://www.postgresql.org/docs/current/backup.html)
- [FastAPI background-task considerations](https://fastapi.tiangolo.com/tutorial/background-tasks/)

## MCP documentation review - 2026-10-07

The two authenticated Jitterbit pages below were reviewed as draft/Beta documentation. They are implementation evidence to validate in the licensed tenant, not a guarantee of deployed feature availability. Reference links deliberately omit authentication credentials.

| Source | Reviewed finding | Implication for this product |
| --- | --- | --- |
| [Jitterbit MCP Service Tokens - draft/Beta](https://draft-extra-e.d7hgs5iasur3d.amplifyapp.com/mcp/mcp-user-interface/mcp-service-tokens/) | Gateway/runtime service tokens authenticate self-hosted private MCP components to the Jitterbit MCP control plane. Cloud-hosted components do not require customer-managed service tokens. These differ from per-server MCP authentication tokens for AI clients. | Keep client-to-MCP, private-component-to-control-plane, MCP-to-APIM and Studio-to-parent credentials separate. Our management REST API/worker is not automatically a Jitterbit private MCP runtime. Do not add private MCP gateway/runtime containers to the baseline without choosing and validating that topology. |
| Same service-token draft | Tokens are environment-scoped; full values are shown only at creation. Tokens cannot be edited/deleted, and deactivation is permanent. | Customer setup must capture the value into protected secret storage at creation. Where private components are selected, qualify replacement-token deployment and verification before deactivating the old token; do not promise reactivation. |
| [Studio MCP Client connector - draft](https://draft-extra-e.d7hgs5iasur3d.amplifyapp.com/integration-studio/design/connectors/mcp-client/) | This is a client of external MCP servers, not a tool publisher. Activities include List/Invoke Tools, List/Read Resources and List/Get Prompts. Connections are included in endpoint usage and licensing. | Baseline tools are published through Jitterbit MCP and backed by APIM/Studio REST operations. The MCP Client connector is optional if a future Studio workflow needs to consume another MCP server. It does not require building a second custom MCP server for the baseline. |
| Same MCP Client draft | Cloud and private agents are supported. Connector updates are downloaded when required; private-agent auto-update can be disabled by organization policy. | Record tested connector/agent/authentication combinations if the connector is selected. Verify connectivity and license/endpoint usage before adoption. Do not apply the listed 3LO agent prerequisite as proof of full protocol compatibility. |
| [MCP specification 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28) and [changes](https://modelcontextprotocol.io/specification/2026-07-28/changelog) | The supplied revision describes stateless requests, per-request version/capability metadata and server/discover; session-handshake behavior differs from prior revisions. | Pin and test the actual protocol revision supported by Jitterbit and each selected AI client. Do not infer vendor compatibility from the existence of the specification. Jitterbit handles its MCP wire protocol; our parent service continues to expose REST contracts. |
| [MCP Tasks extension](https://modelcontextprotocol.io/extensions/tasks/overview) | Optional asynchronous task handles support status polling and result retrieval; support must be declared by client and server. | Retain durable parent job IDs and the get-job tool in the baseline. Native task integration is a separately deferred interoperability candidate. It must not replace persistence, recovery, authorization or require the AI to poll autonomously. Task cancellation is not proof that a remote mutation stopped. |
| [Jitterbit MCP product page](https://www.jitterbit.com/product/mcp/) | Describes managed MCP server creation and reuse of APIs/integrations with governance and policy controls. | Consistent with Jitterbit MCP as the publication layer. Marketing statements do not establish exact transport versions, Tasks support, private-runtime packaging or tenant entitlements; those need technical validation. |

Baseline integration evidence must include the selected MCP hosting mode, supported protocol revision, client authentication, tool discovery/schema behavior, backend APIM authentication, parent API identity, token rotation/revocation behavior, error mapping and job-result retrieval. No documentation-site credential is retained in configuration, references or release artifacts.

## Canonical contracts for the high volume observability upgrade

UPG-001 remains deferred until baseline validation. Its expected data volume is a design input now, not a reason to implement the collectors before the baseline works. The same canonical business fields/types/IDs must pass through MCP, APIM, Studio and management REST; protocol wrappers remain transport-specific. Use a versioned contract family with a shared envelope and separate resource schemas, not one object containing every metric and operation field.

| Domain | Required canonical information | Retrieval shape |
| --- | --- | --- |
| Management job | jobId, action, targetId, accepted profile/release revisions, lifecycle state, times, safe result/evidence reference | One job or bounded job listing |
| PA operation definition | operationId, operationName and available project/environment identity from a qualified provider | Filtered cursor-paginated catalogue |
| PA operation execution | operationRunId, operationId where available, operationName, target/canonical-host/agent/group identity, original and normalized status, submitted/started/finished times, duration or current elapsed time | Filtered time-bounded cursor-paginated executions and one-run detail |
| Host/process metric | Metric name, source timestamp, numeric value, unit/type, host/process identity and permitted dimensions | Current snapshot or selected bounded history |
| PA/JVM/Tomcat/Apache/DB metric | Metric name, value/unit/type, component/agent identity, collection source and support/quality flags | Selected component snapshot/history |
| Summary or export | Applied filters, interval, counts/duration statistics or permitted export reference; coverage, freshness and truncation | Small AI-oriented summary; separately authenticated bounded export |

operationId identifies a definition; operationRunId identifies an execution; jobId identifies management work. They are never interchanged. Local database keys are qualified by their source agent/host so records from different PAs do not collide. Operation IDs/fields absent from the qualified provider are null/unavailable, not inferred from names. Preserve the original PA status alongside normalization; terminal is not equivalent to successful.

Normalize known timestamps to UTC ISO 8601 and preserve source timezone/uncertainty metadata where necessary. finishedAt and durationMs remain null for unfinished runs. Use a separately named elapsedMs when calculating current age. Unknown/missing times do not become zero or the collector's clock. Record observedAt, collection source, source release/provider version and freshness/coverage flags.

List requests require bounded limits, opaque cursors, deterministic pagination and filters for permitted target/agent/group, project/environment, operation ID/name, status and time range. Define snapshot/watermark behavior for records that change from running to finished during pagination. Report nextCursor, returnedCount, applied window and partial/truncated/stale/unavailable reasons. An unsuccessful query is not an empty successful result.

The AI's default queries return summaries, selected metric families and small pages, then drill into a chosen execution or time window. Do not stream the entire PA database/history into a model context. Bulk export is a separate authenticated data route/reference subject to row/byte/time caps and retention; file bytes are not normal tool text.

Incremental collection retains source identity and a checkpoint/overlap policy for new and changed executions, including late finish/error updates and interrupted reads. Metrics distinguish gauges from cumulative counters, preserve units and counter-reset semantics, and define time-bucket aggregation. Raw/history retention, rollups, indexes/partitions, polling frequency, query/response limits and fleet concurrency are qualification/configuration decisions. Benchmark collector load on the PA and management storage before choosing values.

The management job database is distinct from PA TranDb. PA data is read through version-qualified, bounded, fixed read-only providers over the existing permitted transport; no arbitrary SQL or added target listener. Central historical storage is management-owned or an explicitly selected customer observability store. Collection does not depend on the AI continuously asking for data. Sensitive operation payloads/credentials are excluded from default records and exports.

The [canonical data planning contract](jbpa-management-data-contract.json) records domain fields and high-volume rules. It is not yet a runtime JSON Schema or an implemented collector.

## Deployment-readiness learning — 12 October 2026

QA demonstrated that PA registration, core health and Axis HTTP 200 can pass while a required connector adapter is unavailable. The observed invalidation response was HTTP 200 with `status:false`. After the customer updated connectors and tested the saved Gmail connection, logs showed Gmail loaded and the customer confirmed deployment succeeded.

Baseline requirements RDY-001 through RDY-004 capture separate connector readiness, logical-result checks, explicit supported recovery and protected field validation. These checks are proposed, not implemented automatic remediation. See the [learning register](lessons-learned.md) and [evidence report](trandb/token-invalidation-investigation-2026-10-09.md). Historical QA observations do not qualify production sizing or the full management product.

## Composite observability action

UPG-001 adds a proposed `pa_assess_operations` tool/API. Management owns provider fan-out: an explicit target/root or bounded window feeds fixed TranDb, lineage, diagnostic and transfer queries; it returns stage outcomes, descendant failures, evidence and source coverage in one canonical response. Detailed runs/logs are drill-down actions. Trace files, operation attempts and business files remain different grains. See [architecture](trandb/operation-assessment-api.md) and [contract](trandb/operation-assessment-contract.json). The offline assessment harness exists; runtime API, mappings, authorization and production qualification remain deferred.

## Estate health action

The read-only estate-health toolkit implements host/process/pressure, service, TranDb and optional existing Apache/JVM/Tomcat collection plus per-node findings and capacity screening. Proposed estate_assess_health/estate_get_health_assessment routes integrate deep fleet scans with the existing management durable read-work model. See [coverage, capacity rules and Grafana design](estate-health.md). The QA toolkit does not implement fleet Harmony roster discovery, API deployment or production capacity qualification.

## Vendor-owned upgrade correction — 2026-10-14

JBPA triggers the default Jitterbit upgrade installer and monitors its result. It must not suppress vendor startup, restart from verification, re-expand applications or overwrite vendor-restored configuration. The [upgrade contract](vendor-owned-upgrades.md) records the read-only readiness observer, confirmed double-restart/false-success incident and explicit recovery via uninstall/fresh reinstall. Requested older versions are recovery actions, not permission for an unqualified in-place TranDb downgrade. This correction concerns lifecycle correctness; the final skill-security phase remains deferred.
