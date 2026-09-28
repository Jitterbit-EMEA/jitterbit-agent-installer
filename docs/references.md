# References

Reviewed: 2026-09-22. Official English documentation was retrieved through web browsing. These are live pages, not immutable release-specific contracts; capture package metadata, vendor help and sanitized VM evidence before enabling an adapter. VERIFIED below means documented or locally inspected, not runtime-tested.

| ID | Source | Used for / limitation |
| --- | --- | --- |
| J01 | [Linux agents](https://docs.jitterbit.com/agent/linux/) | Package installation, configuration, startup, upgrades and synchronization indicator. Does not establish a complete fresh-install silent recipe. |
| J02 | [System requirements](https://docs.jitterbit.com/agent/system-requirements/) | Current OS list, architecture, sizing and reserved ports; not a historical release matrix. |
| J03 | [Utility programs](https://docs.jitterbit.com/agent/utility-programs/) | Exact configuration flags, service operations, version command and limitations of unattended mode. |
| J04 | [Registration](https://docs.jitterbit.com/agent/register/) | Native Linux register.json path, encrypted credentials, registration fields and persisted identity. |
| J05 | [Access tokens](https://docs.jitterbit.com/management-console/access-tokens/) | Agent Registration token scope; minimum compatible native Linux version still needs confirmation. |
| J06 | [Configuration overview](https://docs.jitterbit.com/agent/configuration-files/) | Configuration ownership and remote editing. |
| J07 | [jitterbit.conf](https://docs.jitterbit.com/agent/jitterbit-conf/) | INI syntax, SSH/SSL fields and named identities. |
| J08 | [Proxy](https://docs.jitterbit.com/agent/proxy/) | Setup/runtime proxy interfaces; command-line credential exposure. |
| J09 | [SSH](https://docs.jitterbit.com/agent/ssh/) | Key configuration and connector selection of named identities. |
| J10 | [Java](https://docs.jitterbit.com/agent/java/) | Bundled runtime, overrides, truststore, keytool and proxy certificate verification. |
| J11 | [Agent logs](https://docs.jitterbit.com/agent/log/) | Main, installer and component log locations. |
| J12 | [Troubleshooting](https://docs.jitterbit.com/agent/troubleshooting/) | Service components, Azure timeout symptoms and identity cloning risks. Not a stable parser specification. |
| J13 | [Allowlist](https://docs.jitterbit.com/getting-started/jitterbit-security/allowlist-information/) | Region-specific outbound destinations and feature-dependent endpoints. |
| J14 | [Private Agent releases](https://docs.jitterbit.com/release-notes/harmony-release-notes/private-agent-releases/) | Release status, compatibility caveats and 11.49 end of life. |
| J15 | [12.10 release](https://docs.jitterbit.com/release-notes/harmony/12-10/) | Regional release schedule; does not approve a project version. |
| J16 | [Harmony troubleshooting](https://docs.jitterbit.com/getting-started/troubleshooting/) | Outbound HTTPS WebSocket connection direction. |
| A01 | [Linux Custom Script Extension](https://learn.microsoft.com/en-us/azure/virtual-machines/extensions/custom-script-linux) | Managed Identity downloads, execution limits, reruns and proxy limitation. |
| A02 | [Run Command comparison](https://learn.microsoft.com/en-us/azure/virtual-machines/run-command-overview) | Managed versus Action Run Command. |
| A03 | [Managed Run Command on Linux](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/run-command-managed) | Guest-agent prerequisite, execution status, timeouts and output. |
| A04 | [Azure cloud-init](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/using-cloud-init) | Initial image customization option. |
| A05 | [Key Vault RBAC](https://learn.microsoft.com/en-us/azure/key-vault/general/rbac-guide) | Secret-read role and separation of control/data planes. |
| A06 | [Linux VM Managed Identity access](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/tutorial-linux-managed-identities-vm-access) | VM identity access to Azure resources. |

## Local evidence

L01: This project directory was empty and was not a Git repository at inspection. No AGENTS.md, installer, config, tests or Azure implementation was present.

L02: Read-only inspection of `/Users/dharish.sewraj/Documents/Projects/AI Engineer - MS Azure/infra-master`: `AGENTS.md`, `CLAUDE.md`, `HANDOVER.md`, `README.md`, `scripts/azure-ai-hello-world.sh`, and `infra/environments/hello-world-network.bicep`. The source implements a hash-approved VNet/subnet deployment only. Searches of `scripts/` and `infra/` found no VM creation or bootstrap execution. No live Azure inventory was queried. Historical handover entries are not current deployment evidence.

## Evidence gaps

No installer URL, package, checksum, installed product, target VM, Harmony credentials or sanitized registration logs were supplied. An attempted `/agent/ssl/` page was inaccessible; SSL claims use the actual `[SSL]` reference J07. Searches did not establish universal registration-success/authentication/environment/proxy parser strings. No undocumented command is approved by this research.

## Phase 1.5 evidence refresh — accessed 2026-09-22

The original register above remains the Phase 0 baseline. Phase 1.5 re-read J01/J03/J04/J05/J06/J08/J11/J12/A01–A05 and added the sources below. All are official vendor/project sources. Web pages and upstream master branches are mutable; package/build-specific conclusions still require captured evidence. No authenticated portal binary retrieval or product/cloud API call was performed.

| ID | Source | Relevant evidence / boundary |
| --- | --- | --- |
| J17 | [Harmony Downloads](https://docs.jitterbit.com/getting-started/harmony-portal/downloads/) | Portal navigation; Linux Debian x64 and release channels. No exact supplied binary URL/build, retrieval authentication/expiry contract or checksum established |
| J18 | [Agent Support Tools](https://docs.jitterbit.com/agent/agent-support-tools/) | Interactive launcher and command grammar; connection-check/service-status; no stable exit-code or JSON contract for those two; Linux report PostgreSQL limitation |
| J19 | [Private agents — Agent status](https://docs.jitterbit.com/management-console/agents/private/#agent-status) | Running means ready for operations; agent ID/group/status UI evidence, not an automation API |
| J20 | [Console AI Assistant](https://docs.jitterbit.com/management-console/console-ai-assistant/) | Agent/status inquiries through UI; no public machine API established |
| J21 | [Citizen Integrator recipe creation](https://docs.jitterbit.com/developer-portal/citizen-recipes/creating-new-recipes/) | Agent model includes status; insufficient for a current supported status-query contract |
| J22 | [Listening service](https://docs.jitterbit.com/agent/listening-service/) | Documented local cluster/listener REST status; not equivalent to Harmony control-plane Running |
| D01 | [Debian dpkg-deb manual](https://manpages.debian.org/bookworm/dpkg/dpkg-deb.1.en.html) | --field/--info inspect metadata; no Jitterbit package values inferred or commands executed |
| A08 | [Blob versioning](https://learn.microsoft.com/en-us/azure/storage/blobs/versioning-overview) | Distinct immutable versions; pin version/digest, consider retention |
| A09 | [Immutable Blob storage](https://learn.microsoft.com/en-us/azure/storage/blobs/immutable-storage-overview) | Version/container retention options and locked-policy constraints |
| A10 | [Blob lifecycle management](https://learn.microsoft.com/en-us/azure/storage/blobs/lifecycle-management-overview) | Policy-driven tier/deletion; project excludes referenced/in-use artifacts |
| A11 | [Blob data access roles](https://learn.microsoft.com/en-us/azure/storage/blobs/assign-azure-role-data-access) | Managed Identity principal, scoped data roles and propagation delay |
| A12 | [CSE upstream cmds.go](https://raw.githubusercontent.com/Azure/custom-script-extension-linux/master/main/cmds.go), [exec.go](https://raw.githubusercontent.com/Azure/custom-script-extension-linux/master/main/exec.go), [files.go](https://raw.githubusercontent.com/Azure/custom-script-extension-linux/master/main/files.go) | Sequence suppression, 4KiB output tails, shell subprocess, local stream files, file preprocessing. Source observations, not pinned deployed-handler guarantees |
| A13 | [CSE upstream README](https://github.com/Azure/custom-script-extension-linux) | Managed Identity download support and guest log/output locations |
| A14 | [Azure Linux Agent service](https://raw.githubusercontent.com/Azure/WALinuxAgent/master/init/waagent.service) | Default service has no alternate User; with A12 supports root-context inference. Verify actual image effective UID |

### Material findings and limits

- J04's Introduction, restart and automatic-registration sections explicitly address Linux, proxy incompatibility and native register.json location. Native applicability is documented; exact-build qualification is not.
- J03's Harmony option table documents parameterized registration and credentials-file input. Its unattended switch has a database caveat. File grammar, secure stdin/env and output secrecy require package inspection.
- J05 identifies Agent Registration scope, environment selection, Admin creation and activation/deletion controls. No lifetime or existing-session revocation behavior is established.
- J06 distinguishes runtime configuration files and remote jitterbit.conf editing. Do not infer that editing ordinary config is a substitute for registration.
- J11 documents installer/main/component logs. J12 describes service diagnostics, Running and cloned-identity collisions, but does not define a universal exact registration-success parser.
- A01 establishes Ubuntu22.04 support, CSE2.1+ MI downloads, protected-setting requirements, one-shot/rerun constraints, noninteractive behavior, 90-minute limit and no native proxy/reboot continuation. A02/A03 establish Managed versus Action Run Command differences. A04 separates cloud-init execution from VM provisioning success.

Official-domain searches for PA12.10 SHA256/package signatures did not establish vendor integrity material. Download transport authentication/URL expiry was not observed. Searches across registration, utilities, support tools, Management Console, Developer Portal/Citizen Integrator, listening service and Console AI did not establish a current supported authoritative cloud-status API. These are bounded negative findings, not assertions that a vendor capability cannot exist. An attempted upstream CSE downloader source fetch failed (429/cache miss); no exact download retry schedule is claimed.

Phase 1.5 local evidence L03: all baseline docs, YAML/schema files, Phase 1 source, launchers, tests and scripts reviewed; before/after hashes verify implementation/config/test/script files unchanged. Regression details are in [validation](phase-1.5-validation.md). No installed Jitterbit product or target Linux VM was available. See [dependencies](dependencies.md) for remaining work.

## Supplied live evidence — captured 2026-09-23

LIVE-PA-1292-U2404 is the sanitized user-supplied manual VM evidence for PA 12.9.2.2 on Ubuntu 24.04.5 LTS amd64, native `.deb`, Agent Registration token, no proxy and Harmony EMEA West. It proves the runtime paths and composite registration/health signatures recorded in the [evidence index](../evidence/README.md). It does not supply a trusted package digest and does not qualify PA 12.10 on Ubuntu 22.04.
