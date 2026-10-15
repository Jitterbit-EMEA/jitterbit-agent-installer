# Skill access and production security architecture

Decision recorded 2026-10-13. Status: **agreed design; deferred final implementation phase; not implemented**.

The immediate concern is the JBPA skill running through Codex/Claude, rather than the proposed Jitterbit MCP solution. This decision records the future security boundary without changing the current QA caller, skill instructions, credentials, SSH configuration or running agents. Implement this phase only when the user explicitly requests it, after the selected functional work is complete. Deferral is not permission to use the current QA access model in production: these controls must be implemented and qualified before production access is enabled.

## Current boundary and required change

The current caller accepts a local private-key path, executes SSH commands and invokes privileged JBPA lifecycle commands. Host-key pinning and protected credential files are useful controls, but do not prevent a process able to use those credentials from issuing a harmful action. A key need not be included in an LLM prompt for the AI-controlled execution environment to have authority to use it.

The production skill must instead submit structured requests to a customer-controlled execution boundary. The model-facing process must not have production keys, access to a credential-bearing SSH agent, unrestricted production SSH, privileged worker administration or approval authority. This architecture does not depend on MCP: the skill can use a narrow broker client. A future MCP adapter may reuse the same boundary, but is not the implementation target of this phase.

| Component | Responsibility | Authority boundary |
| --- | --- | --- |
| Codex/Claude and JBPA skill | Ask questions, submit named diagnostic requests or change proposals, explain sanitized results | No production secrets, shell execution, arbitrary SQL, raw script upload or self-approval |
| Customer request broker | Authenticate caller; resolve inventory; validate action/parameters; enforce policy | Caller-supplied target labels, roles and approval flags are untrusted |
| Monitoring executor | Run reviewed health, metrics, operation and log collectors | Dedicated read-only identity; cannot invoke lifecycle actions or obtain change credentials |
| Independent approval workflow | Present exact impact; authenticate human approvers; issue bounded execution permission | Outside the AI session; no approval tool or approver credentials available to the AI |
| Change executor | Revalidate approved plan and target state; execute one fixed lifecycle action | Separate identity and credentials; no general-purpose AI shell |
| Existing target SSH and JBPA | Enforce forced-command wrapper and narrow local privileges | No additional target daemon, web service or listening port |
| Customer secret store and audit destination | Issue scoped credentials; retain protected audit evidence | AI process cannot read secrets or modify audit/policy state |

Ordered monitoring flow: **skill request → broker policy check → read-only collector over existing SSH → bounded redaction → skill response**. Target temporary diagnostic files are permissible only through reviewed fixed collectors; monitoring must not change PA configuration, registration, packages or service state. The existing QA approach of uploading Python and executing it with sudo must not be carried into production monitoring.

Ordered change flow: **skill proposal → exact immutable plan → independent human approval → change executor revalidation → fixed target action → evidence and result**. The AI can view proposal status but cannot approve it. Install, upgrade, uninstall and deregistration all use this workflow. Local uninstall and removal of a Harmony agent record are separately named actions and separately authorized; an uninstall approval does not implicitly approve deregistration.

## Enforcement and approval contract

Production monitoring is read-only by default. Server-owned inventory binds customer, environment, canonical host, agent and group identities. Names or request fields cannot downgrade production to QA. Separate production/non-production identities, network access and credential stores prevent a QA path from bypassing production policy. Authorization is checked both at admission and immediately before execution; policy, identity or evidence failures block the change.

An approval binds the requester, authorized approver, customer, environment, canonical host, observed agent/group identity, action, exact release/digest where applicable, plan revision/hash, approved change window, expiry and unique execution ID. It is single-use and cannot authorize modified parameters or a second job. Retries for the same job reconcile the recorded outcome rather than replaying a potentially completed mutation. Destructive production actions require independent two-person approval; the requester cannot approve their own proposal. Ordinary chat confirmation is not an approval credential.

Before a lifecycle action, recheck target identity, appropriate active-operation/drain conditions, remaining group capacity and maintenance policy. Fresh install validates the expected host/group and absence or known state of an agent; it does not require an already-existing agent identity. For uninstall/deregistration, confirm the exact affected agent record and retain explicit local/Harmony outcome evidence. Unknown outcomes enter reconciliation; do not blindly retry destructive actions. Serialize changes per canonical host and reject changed or expired approvals under that ownership boundary.

## Credential and transport choices

Support dedicated management-held SSH credentials as a migration option, short-lived SSH certificates from a customer CA, or an existing enterprise PAM broker. Cloud management-plane execution is an optional separately qualified adapter; it does not automatically remove privileged execution risk. Do not require a new secrets platform when a suitable customer platform already exists.

Short-lived certificates still use a private key inside the executor. Expiry limits subsequent authentication, not an already-established command/session. SSH-agent or non-exportable-key access also grants signing authority and must remain inaccessible to the AI process. Scope identities by customer/environment and monitoring/change role, pin host identity, disable shell/PTY/forwarding where unnecessary and use root-owned fixed wrappers with strict argument parsing. Narrow sudo rules must not allow shell interpreters or writable executables/configuration as an escape path. Credential issuance, rotation and revocation remain customer-owned.

Log and TranDb responses may contain customer data even when credentials are protected. Return bounded, redacted, allowlisted fields; retain sensitive raw evidence under customer control and restrict drill-down access. Treat log text, Markdown and tool output as untrusted data that cannot grant permissions or redefine actions. Policy enforcement must remain independent of model behaviour.

## Final-phase acceptance and rollout

Record these requirements as SEC-SKL-001 through SEC-SKL-014 in the [canonical matrix](jbpa-management-requirements.json). This phase follows the selected baseline/upgrade functional work and begins only on an explicit implementation request. Existing QA authorizations do not grant production access. No skill/runtime security implementation is included in this documentation update.

Qualify the broker and restricted collectors in QA, then a canary non-production environment. Before production, prove that a monitoring identity cannot uninstall, upgrade, install, deregister, restart, modify configuration or access lifecycle credentials through any direct or indirect route. Test arbitrary command/script/SQL/path injection, forged identity, production-as-QA spoofing, prompt injection in logs, approval replay, altered plans, self-approval, expiry, concurrent jobs, policy outages and uncertain remote outcomes. Retain independent audit records of allowed and denied requests, approvers, plan hashes, credential issuance references and execution evidence without secrets.

Provide an operator-controlled kill switch that blocks new mutations and revokes new credential issuance; describe separately how already-running actions are safely reconciled. Rollback disables production access rather than restoring unrestricted workstation SSH. No production readiness claim is valid until negative authorization tests and customer security sign-off pass.

## Architecture document boundary

This is the current skill-specific architecture addendum, linked from the management specification and HLA index. The historical v8 PDF is unchanged and does not include these controls. The MCP architecture is not being rebuilt or deployed by this decision.
