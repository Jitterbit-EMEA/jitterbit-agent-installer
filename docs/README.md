# Documentation index

Current product contracts: [architecture](architecture.md), [configuration](configuration.md), [health](health-contract.md), [lifecycle](lifecycle-management.md), [security](security-review.md), [Azure AI Agent](azure-ai-agent-contract.md), [readiness](production-readiness.md), [version matrix](version-qualification-matrix.md), [errors](errors.md), [Phase 2G](phase-2g-summary.md).

Operational runbooks: [customer short path](customer-start-here.md), [customer detailed install or upgrade](customer-install-runbook.md), [install](runbooks/install.md), [uninstall](runbooks/uninstall.md), [health](runbooks/health.md), [diagnostics](runbooks/diagnostics.md), [enterprise truststore](runbooks/enterprise-truststore.md), [new version](runbooks/onboard-new-pa-version.md), [latest change](runbooks/handle-latest-pa-change.md).

AI integration: [current Codex / Claude Code skill and RC9 remote caller](integrations/skills/README.md); [historical RC3 Claude Code kit](integrations/claude-code/README.md).

Preserved evidence reports: [Phase 2C](phase-2c-summary.md), [Phase 2D](phase-2d-summary.md), [Phase 2E](phase-2e-summary.md), [Phase 2F](phase-2f-summary.md). Earlier phase documents are historical and their dated readiness statements do not override current qualification. Original evidence is immutable; later interpretations are separate artifacts.

## Phase 3B external handoff

- [Canonical orchestrator contract](external-orchestrator-contract.md)
- [Pre-provisioned host contract](pre-provisioned-host-contract.md)
- [Phase 3B summary](phase-3b-summary.md)

## Phase 3C runtime completeness

- [Phase 3C summary](phase-3c-summary.md)
- [Structured preflight](preflight-contract.md)
- [Reinstall runbook](runbooks/reinstall.md)

## Management product and accumulated research

- [Consolidated learning register](lessons-learned.md): retained design decisions, QA findings, recovery, limitations and executable requery paths.
- [Management product specification](jbpa-management-product.md) and [requirements matrix](jbpa-management-requirements-matrix.md).
- [TranDb research and capture workflow](trandb/README.md), [knowledge catalogue](trandb/knowledge-catalogue.json) and [deployment recovery investigation](trandb/token-invalidation-investigation-2026-10-09.md).

Estate observability: [expert health architecture and QA toolkit](estate-health.md).

- [Vendor-owned upgrade behavior](vendor-owned-upgrades.md) and [12.11.3.2 live QA validation](upgrade-12.11.3.2-qa-validation.md).
- [Portable sanitized upgrade evidence](../evidence/pa-12.11.3.2/fixed-upgrade-2026-10-15.json); generated captures and candidates stay local under ignored `output/`.

- [Interactive read path and measured performance](read-path-performance.md): focused modes, preserved security controls and repeatable benchmarks.
