# Discovery questions and gates

Updated 2026-09-22. These questions block only dependent work; they do not prevent local schema/dry-run design. Do not send passwords, tokens or private keys in chat or commit them to Git.

## Confirmed by the user

- First test OS: Ubuntu 22.04.
- First test Private Agent release: 12.10.
- Azure AI Agent belongs to the same `AI Engineer - MS Azure` repository; another person built the actual agent. The inspected checkout does not contain that implementation.

## Mandatory before implementation of the dependent capability

| ID | Question / evidence needed | Gate |
| --- | --- | --- |
| M01 | Provide the 12.10 Ubuntu amd64 `.deb` download URL, exact build and trusted checksum/signature if available. Can the artifact be mirrored privately? | Real catalogue approval and Phase 2 download/install. |
| M02 | Where is the actual agent's source/tool contract: subdirectory, branch/commit or deployed API specification from its author? What VM resource IDs/result fields does it return? | Exact Azure integration hook, Phase 3. |
| M03 | What Harmony region, organization, environment and agent-group ID/name should the test use? What agent naming convention and collision policy? | Registration adapter and test. |
| M04 | Is an environment-scoped Agent Registration token available for native Linux 12.10? Otherwise provide vendor confirmation of secure credential-file input format and noninteractive behavior. | Secure Phase 2 registration. |
| M05 | Can the chosen package/help output confirm fresh-install unattended behavior, package dependencies (including the documented Python 2 step), service auto-start behavior, unit/init integration, account ownership and component status? | Base lifecycle implementation. Obtain evidence from vendor or approved disposable VM. |
| M06 | Provide sanitized current-version successful registration/start logs and failed-auth/group/network/TLS/proxy examples, or a supported authoritative Harmony-status API contract. Which identity fields correlate the VM to Harmony? | Health parser and automated SUCCESS verdict. Absence of samples means fail closed. |
| M07 | Are narrowly controlled memory-backed transient credential files allowed where the vendor requires a file? What persistent product credential/private-key storage is permitted? If zero plaintext persistence is absolute, can vendor mechanisms satisfy it? | Any file-based token, passphrase or key adapter. No policy exception is assumed. |
| M08 | Does the test VM have direct permitted outbound access, or is corporate proxy/custom CA mandatory from first connection? | Phase 2 dependency order. Mandatory proxy means scope revision before base lifecycle validation. |

The initial OS/release selection is resolved. It does not approve deployment, supplied packages, production suitability or the next implementation phase. Phase 1 can be authorized with pending placeholders and denied unsupported adapters; it must not manufacture answers to M01–M08.

## Required before production

| ID | Question / decision |
| --- | --- |
| P01 | Azure tenant/subscription/resource group/region, approved VM image URN/version, SKU, disk layout, OS maintenance and deployment permissions? |
| P02 | System-assigned versus user-assigned identity; dedicated Key Vault, role assignment owner, secret naming/version pinning, rotation/revocation and expiry policy? |
| P03 | Private endpoint requirements, DNS, artifact/package mirrors, outbound internet/proxy policy, NAT/WebSocket idle timeout and reviewed region/feature allowlist? |
| P04 | Harmony licensing, SSO/MFA/access policy, agent-group/environment mapping, existing group agent versions and capacity? |
| P05 | SSH server host-key verification, key algorithms/formats, passphrase handling, named identities and required connector tests? |
| P06 | PEM client certificates/private keys, expiry/rotation, approved CA fingerprints, effective JVM override policy and truststore password handling? |
| P07 | Host workload sizing, installation free-space policy, timeout based on synchronization size, concurrency and Harmony registration rate limits? |
| P08 | Ownership of remotely editable configuration; retention/redaction/access for vendor logs, results and encrypted backups? |
| P09 | Egress package licensing, SBOM/provenance, supported release policy, vulnerability review and checksum approval process? |
| P10 | Maintenance/drain windows, backup restore testing, approved upgrade edges, connector/plugin compatibility and recovery after database migration? |
| P11 | Required workload smoke operation proving end-to-end processing beyond registration; owner and acceptance thresholds? |

## Optional enhancements

- Non-root/RPM/Amazon Linux adapters after explicit platform evidence.
- Other cloud providers and non-Azure secret providers.
- Fleet scheduling, rolling upgrades, autoscaling registration/deregistration policy.
- Image baking with no registered identity or secrets in the image.
- Central metrics/dashboard, policy signing and automated release qualification.

## Phase 0 decision

Stop here. Review the documentation and resolve/assign the questions relevant to the next phase. No production installer, schema loader, Azure bootstrap or lifecycle script was created. Phase 1 should be a local, testable framework only; Phase 2 needs the real artifact and registration evidence plus a disposable test VM.

## Phase 1 dependency register

Phase 1 was explicitly authorized on 2026-09-22. The Phase 0 gate above is historical; the active gate is now stop after the framework foundation. All original M/P questions remain unresolved unless marked confirmed above.

| Dependency | Description | Related questions | Framework treatment |
| --- | --- | --- | --- |
| DEP-001 | PA 12.10 exact package URL/build, trusted integrity and package behavior | M01/M05 | Known version, null package evidence, installable=false |
| DEP-002 | Verified secure unattended registration and secret storage | M03/M04/M07 | Interface only; no resolved credentials or real registration |
| DEP-003 | Authoritative current registration/service health evidence | M06 | No log success patterns or simulated health; runtime fields null |
| DEP-004 | Actual Azure AI VM-provisioning implementation/tool contract | M02 | Provider boundary only; no Azure calls |

Test-network requirements (M08), credentials/keys policy and production questions remain additional gates for their respective runtime phases.

## Phase 1.5 reconciliation — current gate

Stop after Phase 1.5. The Phase 0/1 stop points above are historical. Current dependency states are in [dependencies](dependencies.md); documentation has reduced uncertainty, not enabled runtime execution.

| Question | Current disposition | Remaining input |
| --- | --- | --- |
| M01 | PARTIALLY_RESOLVED: package type/acquisition/intake designed | Actual exact package/provenance, integrity material if available, mirror entitlement |
| M02 | PARTIALLY_RESOLVED: Azure handoff contract designed | Provisioning author's source path/branch/commit or actual tool specification |
| M03 | BLOCKED: test identity not supplied | Non-production region/org/environment/group and naming |
| M04 | PARTIALLY_RESOLVED: documented token/native file and parameterized alternatives | Chosen strategy, native12.10 test, token lifecycle or credentials-file grammar |
| M05 | BLOCKED: package behavior unobserved | Artifact/help/scripts and controlled installation evidence |
| M06 | PARTIALLY_RESOLVED: composite evidence model/test plan defined | Current-build fixtures, tool codes and supported cloud-status contract; manual Console evidence for tests |
| M07 | BLOCKED: materialization policy unresolved | Accepted transient-file handling and persistent encrypted identity policy |
| M08 | BLOCKED: network unknown | Direct Harmony egress or proxy/custom CA requirement; auto-registration prohibited with required Harmony proxy |

Required next input set: package + non-production target + selected secure registration strategy + available approved test VM, followed by explicit Phase 2 authorization. No secret values in chat. The actual Azure hook is necessary for the Azure integration work, but need not prevent separately authorized portable adapter testing on an existing test VM. P01–P11 remain production gates.
