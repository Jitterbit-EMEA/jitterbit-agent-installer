# Changelog

## 0.3.0 — 2026-09-23

Phase 2B adds Managed Identity Key Vault resolution, private Blob artifact retrieval, an Azure-facing bootstrap command with v2 result, a hash-verifying Custom Script wrapper, offline release builder, secret cleanup, stale-log protection, and a sanitized PA 12.10 regression harness. The user-supplied PA 12.10.1.1 URL is pending digest approval. Read-only inspection found that the supplied VM is Ubuntu 24.04 with PA 12.9.2.2 and no working Managed Identity response.

## 0.2.0 — 2026-09-23

Phase 2 native Linux adapter for the evidence-qualified `.deb` and `register.json` workflow, composite runtime health parser, explicit failure states, sanitized evidence bundle, and 16 focused lifecycle/failure tests. PA 12.10 on Ubuntu 22.04 and package artifact approval remain pending.

## 0.1.0 — 2026-09-22

Phase 1 read-only framework: strict configuration/catalogue/result schemas, OS detection, approved-support lookup, local preflight, planning, diagnostics, guarded state, centralized errors/logging, secret abstraction and test-only provider. Real vendor and cloud execution remain disabled.

## Phase 0 — 2026-09-22

Official documentation research and architecture proposal. No implementation or real installation validation.

## Phase 1.5 — 2026-09-22

Evidence refresh, registration/health/artifact/Azure decisions, schema proposal, dependency reconciliation and controlled Phase 2 specification/test plan. Documentation only; no runtime source, schema, configuration or test changes. Phase 0/1 history preserved with current-decision pointers.
