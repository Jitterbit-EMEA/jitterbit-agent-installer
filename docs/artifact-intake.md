# Artifact acquisition and intake design

Status: DESIGNED; DEP-001 PARTIALLY_RESOLVED. Nothing downloaded, extracted, installed or uploaded in this phase.

## Established facts and gaps

J01 documents Ubuntu installation using a Debian amd64 package with the naming pattern `jitterbit-agent_<VERSION>_amd64.deb`. J17 identifies Harmony Portal Downloads, Linux Debian (x64), as its acquisition route. The portal presents release channels; a channel label is not an immutable 12.10 build selector.

| Question | Finding |
| --- | --- |
| Exact 12.10 filename/build | Not supplied; filename pattern must not be substituted for metadata |
| Stable direct URL | Not established by the reviewed public pages |
| Authentication | Portal navigation is documented; authenticated administrative retrieval is the proposed intake route. Final binary URL authentication was not observed |
| Temporary/signed/session-specific URL | Unknown; do not assume either public permanence or expiry |
| SHA256/SHA512/signature/signing key | None located for this package in the reviewed pages and official-domain searches. This is not proof that Jitterbit supplies none privately |
| Package fields | D01 documents `dpkg-deb --field` and `--info`; Package, Version, Architecture, Depends and Pre-Depends can be inspected without installation. Actual values unknown |
| Internal mirroring | Technically suitable; entitlement/contract and support conditions must be confirmed by the owner/vendor before distribution. Public installation docs are not redistribution permission |

## Controlled workflow

1. An authorized administrator retrieves the selected build, recording UTC time, source page, release selection, original filename, size and retriever identity. Do not preserve portal cookies or signed URL query strings in evidence.
2. Intake copies bytes into a quarantined private area. Compute SHA-256; record that it is locally computed. Obtain vendor signature/digest if available, verify using independently trusted key/provenance, and preserve the verification outcome.
3. In an isolated intake environment, inspect control metadata and maintainer scripts **without executing them**. Record dependency versions, service startup, users/groups, paths and prompts. Compare marketing release 12.10 with the exact Debian version; do not assume equality. Debian `amd64` maps to framework `x86_64`.
4. Review source provenance, malware/vulnerability findings and mirror entitlement. A locally generated checksum proves subsequent byte consistency, not vendor authenticity. If upstream verification is unavailable, require an explicit provenance acceptance record, never label it vendor-verified.
5. Publish the reviewed bytes to a private staging blob with a content-addressed object name; verify bytes again after transfer. Record storage account/container/key and immutable version ID independently of a URL query.
6. Propose a catalogue change containing real build, SHA-256, provenance, intake reviewer, adapter profile and test qualification. Run catalogue/schema regression checks.
7. Authorize a named non-production qualification run against the VERIFIED artifact. After its evidence is reviewed, a separate approver can promote the exact digest to APPROVED. Upload never grants deployment approval. Production eligibility is a separate qualification field.

Future tooling may use `dpkg-deb --field PACKAGE.deb Package Version Architecture Depends Pre-Depends` and `dpkg-deb --info PACKAGE.deb` on a supplied package after authorization. These commands were not run. Do not source package scripts or trust embedded checksums as independent provenance.

## Intake lifecycle

| State | Entry condition | Deployment use |
| --- | --- | --- |
| DISCOVERED | Release/source identified | None |
| IMPORTED | Quarantined bytes and locally computed digest recorded | Inspection only |
| VERIFIED | Provenance decision, metadata, dependency/security review complete | Explicitly authorized non-production qualification only |
| APPROVED | Reviewer and qualification evidence bound to exact digest/target | Only named approved environment classes |
| DEPRECATED | Superseded but retained for traceability/recovery | No new deployment without separate exception |
| BLOCKED | Integrity, provenance, compatibility or policy failure | None; cannot resolve via alias |

Any state can become BLOCKED. Re-verification creates a new review record. A changed byte stream is a new artifact even when release/name matches. Do not mutate an old approval. Keep production qualification separate from package provenance and mock-test status.

## Recommended Azure store

Use a private Blob container, public anonymous access disabled, HTTPS, reviewed network access and VM Managed Identity with **Storage Blob Data Reader** scoped to the approved container (A11). Intake/publishing uses a different write identity; the VM cannot upload or approve artifacts. Keep quarantine, approved software and runtime evidence in separate containers with separate access policies.

Blob versioning preserves distinct immutable versions (A08), but does not by itself prevent deletion. Pin both object version and digest. A trusted reviewed catalogue/manifest must carry the digest; a mutable checksum beside a mutable binary is insufficient. Consider version-level time retention for approved artifacts (A09); storage owners select retention before locking. Do not create a locked policy in this phase.

Lifecycle rules (A10) may tier/delete retired content only after rollback/support retention and catalogue-reference checks. Exclude currently approved versions and in-use recovery artifacts from deletion or archive tiers that would prevent immediate retrieval. Retain provenance/approval records at least as long as the artifact. Test private DNS and RBAC propagation from the guest; private Blob access does not provide Harmony connectivity.

No account keys, SAS, credentials or registration files belong in Git, ordinary config blobs or catalogue URLs. Azure provider resolves the non-secret blob locator into an authenticated request in memory. Preserve the existing schema's rejection of arbitrary signed URLs; see [schema proposal](schema-change-proposal.md).
