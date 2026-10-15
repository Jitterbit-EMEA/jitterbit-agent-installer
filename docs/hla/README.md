# JBPA Management HLA

Security architecture addendum, 2026-10-13: [skill access and production security](../skill-security-architecture.md) addresses the JBPA skill's credential and execution boundary. Production monitoring is read-only; install, upgrade, uninstall and deregistration require independent approval. SEC-SKL is deferred until an explicit implementation request and runs last among selected functional phases, before production access. No skill/runtime controls or PDF were changed by this planning decision; v8 does not contain this addendum.

The current document is `../../output/pdf/JBPA_Management_High_Level_Architecture_v8.pdf`.

Version 8 retains the approved Version 7 page master and refines its native-vector figures. It follows the Opportunity Intelligence document composition: transparent logo, framed title panel with orange accent, shaded content cards, dark table headers, alternating rows, grouped architecture zones and a shared footer. Tables and containers were restructured, not removed. Full technical table content, technology explanations, narrative sections and callouts are retained.

## Structure

33 pages follow seven chapters: product and context; technology and components; delivery and execution; contracts; security and recovery; deployment and operations; reuse and evidence. Eight technical figures explain the ordered lifecycle, target resolution, durable admission, queue dispatch, remote execution, job ownership, reconciliation and result retrieval. Page 4 has ten ordered actions across three phases and gives the management host most of the drawing space. Fleet and data blocks align on common rows; all component cards are white with teal top bars on grey parent zones. Sequence diagrams use larger aligned actor headers and a separate numbered row axis. Queue dispatch and host execution use separate sequences, with shared actor spacing, numbered calls, activation marks and explicit request/response styles.

## Sources

- `rebuild/content-source.json`: technical content snapshot used for the reconstruction.
- `rebuild/model.json`: generated current 33-page document model.
- `../../scripts/hla/rebuild/document.py`: current document renderer.
- `../../scripts/hla/rebuild/figures.py`: new editable native-vector diagram definitions.
- `../../scripts/hla/rebuild/validate.py`: PDF and figure validation.
- `../../output/hla/rebuild/diagrams/`: eight SVG exports from the same drawings embedded in the PDF.
- `../../output/hla/rebuild/layout.json`: measured page content boundaries.
- `../../output/hla/rebuild/qa.json`: structural and geometry checks.

The design references are the Opportunity Intelligence shared report renderer, customer reference renderer, user guide and immutable Esker/Sealey architecture examples. Their typography, component roles, spacing and hierarchy informed this rebuild. Reference-project files were not modified. Superseded HTML/Mermaid renderers, duplicate source models and earlier draft exports were removed in the 15 October cleanup. They remain recoverable from Git commit `dfe797e`; the current native-vector build is retained. Brand/source provenance is preserved in `assets/style-provenance.json`.

## Build and verification

```bash
python scripts/hla/render.py
```

Use the document-only Python dependencies in `scripts/hla/requirements.txt`; validation also uses `pdfplumber`. The current authoring environment has Arial fonts under `/System/Library/Fonts/Supplemental/`. No browser, remote diagram service or Node renderer is required for this version. The output is local and vector-based.

The renderer measures paragraphs, table rows, node wrapping and sequence label widths. Validation checks PDF pagination and footers, bookmarks, text margins, retained technical content and connector/text intersections. Visual review separately checks all pages and each figure at full size. The QA file's visual status applies to its PDF hash.

This is the proposed product HLA. Document validation is not implementation or production qualification of the management runtime.

## Baseline and subsequent upgrades

The accepted HLA describes the management baseline. The 2026-10-07 [product decision and MCP review](../jbpa-management-product.md) and [upgrade roadmap](../jbpa-management-roadmap.json) defer PA/host observability until baseline validation. Existing basic health and safe-drain checks remain baseline requirements. Native MCP Tasks is a separate compatibility candidate. These decisions do not authorize an upgrade deployment and do not claim that the baseline is functioning.

Baseline contract update, 2026-10-07: `getVersions` / `GET /v1/versions` is now explicit in the product specification, roadmap and editable HLA content. The v8 PDF predates this contract update and has not been regenerated.

Current onboarding decision, 2026-10-07: minimal management bootstrap precedes MCP-driven guide/options/file-transfer/configuration/validation/execution. The earlier AI-assisted terminal installer is superseded as the primary customer flow. The product specification and canonical matrix hold these decisions; PDF v8 has not been regenerated for these scope refinements.

The [requirements matrix](../jbpa-management-requirements-matrix.md) now tracks MCP-driven setup, multi-host file selection, group/profile changes and all deferred options using stable IDs; its canonical JSON is the requirements record.

Planning update, 2026-10-08: the active baseline uses the PostgreSQL READY job backlog directly. JBMQ/outbox/dispatch is superseded; PDF v8 and the earlier ten-step queue picture are historical views. UPG-001 high-volume domain contracts, operation IDs/timestamps, paging and collection rules are retained in the requirements matrix and data planning contract.
