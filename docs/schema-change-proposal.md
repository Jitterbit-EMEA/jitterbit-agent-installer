# Schema change proposal — Phase 2

Proposal only, 2026-09-22. All four actual schema files, catalogues, examples and Phase 1 source remain unchanged. No fabricated package URL, checksum, build or approval has been added.

## Retain and extend deliberately

Retain strict unknown-key rejection, secret-reference objects, version precedence, exact platform matching, signed-URL rejection and no runtime providers in dry-run. Python >=3.10/thin Bash and current interfaces remain the baseline. Do not restructure the whole versions catalogue merely to match a conceptual example.

| Area | Current v1 | Proposed v2 |
| --- | --- | --- |
| Registration | nullable strategy: register-json-token or credentials-file | Discriminated mode: interactive, jitterbit-config, auto-register; distinct authentication branch |
| Authentication | token or username/password references | access-token, username-password, vendor-encrypted-pair; never inline values; mutually exclusive required refs |
| Mode constraints | Limited strategy conditionals | interactive requires TTY; jitterbit-config requires pre-created exact agent/group/organization; auto requires group ID/name prefix and rejects Harmony proxy |
| Timing | registration timeout, poll interval | Retain limits; add bounded vendor retry count/interval and per-probe cap with cross-field budget checks |
| Lifecycle | persistent default false deregistration | Keep persistent false; re-registration must be explicit operation/profile, not a rerun side effect |
| Secret materialization | unresolved | Approved materialization profile reference, qualification evidence and cleanup policy; no default persistent plaintext exception |
| Artifact | flat URL/build/sha256 fields per platform | Keep artifact list; add provider-specific non-secret locator (azure-blob account/container/key/version_id or approved local intake path), independent integrity/provenance/approval records |
| Approval | pending/approved/denied at release | Per-artifact intake state plus qualification scope; exact digest-bound approvals, separate production evidence |
| Results | changed=false, runtime null; no live states | Explicit version 2 runtime schema with reason codes, lastCompletedStage, cleanup status and individually sourced nullable observations |

An Azure Blob version ID is a structured locator field, not permission to allow arbitrary signed query strings through the current URL validator. Local artifacts still require verified provenance/digest. Configuration references a reviewed adapter profile; no arbitrary shell commands or permissive provider imports.

Use JSON Schema oneOf branches with const mode/authentication selectors and additionalProperties=false. Interactive must reject secret references that are not used; auto-token must reject username/password fields; encrypted-pair must not accept a plaintext pair in its place. Runtime checks enforce profile qualification, filesystem ownership, group/environment association and network constraints beyond schema structure.

## Migration and compatibility

Build v2 loaders/result consumers and tests together only after Phase 2 authorization. Keep v1 validation/dry-run behavior stable; do not auto-convert `credentials-file` until its format/semantics are confirmed. Provide explicit migration output for review. Reject v1 runtime execution rather than reinterpret ambiguous settings. Aliases resolve only to approved platform artifacts; VERIFIED-only lab use needs an explicit non-production qualification policy binding exact digest and test request. Never set production approval to bypass intake tests.

New results should distinguish REGISTERED evidence from local health and cloud Running. Keep unknown as null. Retain one final JSON, guarded terminal states, explicit new-file output, safe error messages and history. Add per-step mutation evidence so changed may be true even on failure. No fake success to make CSE green.

## Qualification before implementation

Review this proposal, choose registration/network/materialization policy, supply package evidence and target. Then test migration, incompatible combinations, proxy rejection before mutation, qualification gates, output compatibility, finite budgets and failure cleanup. Existing 76 tests remain unchanged in Phase 1.5. See [implementation specification](phase-2-implementation-spec.md) for states and exit-code reconciliation.
