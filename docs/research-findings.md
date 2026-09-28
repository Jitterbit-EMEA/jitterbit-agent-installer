# Research findings

> Phase 1.5 addendum (2026-09-22): historical Phase 0/1 content below is preserved. Current readiness and reconciled decisions are in the [Phase 1.5 summary](phase-1.5-summary.md), [dependency register](dependencies.md) and [Phase 2 specification](phase-2-implementation-spec.md). Runtime code/schemas remain Phase 1.

Reviewed 2026-09-22. Source IDs link to [references](references.md). Labels: **VERIFIED** = public documentation or inspected source; **REASONABLE ENGINEERING DESIGN** = proposed implementation choice; **ASSUMPTION** = tentative project default; **REQUIRES CONFIRMATION** = blocked behavior. None of the product findings is runtime validation.

## Linux installation and release support

**VERIFIED — J01:** Ubuntu uses a `.deb` installed with `dpkg --install`; Red Hat uses `.rpm` with `yum install`. A separate Red Hat non-root `.tar` flow exists. Configuration follows package installation through `jitterbit-config`, then `jitterbit restart`. The installer can bundle PostgreSQL. RPM/DEB installations start with the host; the non-root example creates a user `jitterbit.service`. Upgrades require backups and restart; major upgrades require environment synchronization. The page mentions `silent_install` for upgrade prompts, without a complete fresh-install invocation contract.

**REQUIRES CONFIRMATION:** inspect the chosen package's scripts and dependencies before implementing silent package installation, service auto-start suppression, or prerequisite installation. Do not extrapolate `silent_install`, package-manager `-y`, or `DEBIAN_FRONTEND` into a verified Jitterbit unattended interface. The Ubuntu instructions include Python 2 alternative setup: reconcile this with the selected modern Ubuntu image and vendor guidance, rather than executing it blindly. Non-root is a distinct later adapter.

**VERIFIED — J02:** the current Linux list is RHEL 9, Amazon Linux 2023, Ubuntu 22.04 LTS and Ubuntu 24.04 LTS, for currently supported agents. Minimum hardware is x86_64/amd64, four cores, 8 GB RAM and 50 GB disk with 100 MB/s transfer speed. The reference reserves 46905–46914 for components and documents Linux PgBouncer port 6432. Reserved ports are not an instruction to expose them publicly.

**DESIGN:** initially target one approved Azure x86_64 image. Reject Rocky, Alma, RHEL 8/10 and ARM unless new version-specific vendor evidence explicitly permits them. Amazon Linux support does not imply a suitable Azure image exists. Distinguish disk capacity, free install space and workload growth; a free-space threshold is a project policy, not the vendor's disk-capacity specification.

**VERIFIED — J14/J15:** 12.10 has published September 2026 regional releases. 11.49 reached end of life on September 18, 2026. **DESIGN:** retain historical catalogue entries for audit but deny unsupported releases by default. No release is approved for this project yet. Do not derive a complete historical OS matrix from today's generic table.

## Configuration and service interfaces

**VERIFIED — J03:** utilities are exposed under `/usr/bin` with links into `/opt/jitterbit/bin`. `jitterbit version` reports Process Engine version; `jitterbit status` reports Process Engine, Scheduler and Cleanup. Component operations include Apache, Tomcat, PostgreSQL, PgBouncer and VerboseLogShipper. Service-operation syntax changed from underscores to spaces at 11.54. `jitterbit-config` documents `--login-url`, `--user`, `--password`, `--credentials-file`, `--organization`, `--agent-group`, `--agent`. Its `--unattended` description still allows a PostgreSQL administrator password prompt; `--quiet` skips prompts only when one choice exists.

**REQUIRES CONFIRMATION:** native systemd/SysV integration for each RPM/DEB, full component-status output and exit semantics, installed account IDs, credential-file grammar and unattended Harmony behavior. Do not equate one active unit with a healthy agent. Do not use password-bearing arguments.

**VERIFIED — J06:** principal files include `jitterbit.conf`, `jitterbit-agent-config.properties`, Apache `httpd.conf` and `CleanupRules.xml`. Management Console can remotely edit `jitterbit.conf`. **DESIGN:** nominate one owner for managed keys so remote edits and bootstrap do not continually overwrite each other.

Paths to inspect after installation: `/opt/jitterbit/jitterbit.conf`, `/opt/jitterbit/Resources/jitterbit-agent-config.properties`, `/opt/jitterbit/apache/conf/`, `/opt/jitterbit/JdbcDrivers.conf` (J01); identity files are discussed below. These are discovered and checked before any write.

## Registration and secret constraints

**VERIFIED — J04:** native Linux supports `/opt/jitterbit/Resources/register.json`; documented migration removes `credentials.txt` before restarting. Registration produces persisted credentials and consumes the registration file. Fields include `cloudUrl`, `agentGroupId`, `agentNamePrefix`, encrypted `username`/`password`, or `token`, plus retry and deregistration controls. Documented credential encryption uses `jitterbit-utils -e USERNAME PASSWORD`, exposing input in argv. Docker environment-variable examples are not native Linux interfaces.

**VERIFIED — J05:** Agent Registration access tokens can replace username/password in `register.json`; environment scoping is available.

**DESIGN:** prefer a narrowly scoped registration token retrieved from Key Vault if the chosen native build supports it. Otherwise evaluate pre-encrypted credentials in Key Vault or the documented credentials-file interface after validating its format. Do not invent stdin flags or reproduce Jitterbit encryption. Existing registered agents retain their identity; never delete `credentials.txt` as routine rerun behavior. Make re-registration a separate explicit lifecycle operation. Agent-group membership is the registration target; environment metadata alone is insufficient.

**REQUIRES CONFIRMATION:** token minimum version, restart behavior, naming guarantees, identity persistence, permission requirements, SSO/MFA policy and a secure delivery mechanism. A plaintext token in register.json would conflict with the requested no-plaintext-storage rule. A temporary memory-backed file may be feasible only after validating vendor handling and an approved threat model; it is not a proven solution. Product-persisted credentials remain sensitive even when encrypted. No unsupported secret handling is silently enabled.

## Enterprise configuration

**VERIFIED — J08:** Linux setup supports `--proxy-host`, `--proxy-user`, `--proxy-password`, `--proxy-ntlm-domain`; runtime utility options include `--set-http-proxy-host`, `--set-http-proxy-username`, `--set-http-proxy-pwd`, `--set-http-proxy-domain` and `--set-http-proxy-exceptions`. HTTPS proxies require Java trust configuration. **DESIGN:** separate OS/package, downloader, agent, and JVM proxy layers. Never assume `no_proxy` or environment variables configure all four. Authenticated proxy automation is blocked pending a credential channel without argv leakage; no TLS-verification bypass.

**VERIFIED — J09:** `[SSH]` uses `PrivateKeyFile`, optional `PublicKeyFile`, and `PrivateKeyPassphrase`; suffixes select named identities through source/target SFTP variables. **DESIGN:** retrieve keys securely, compare public fingerprints, preserve supplied identities, and test service-account readability. Do not generate replacement keys on reruns. Validate server host-key policy and connector compatibility separately.

**VERIFIED — J07:** `jitterbit.conf` is INI; changes need restart. `[SSL]` supports PEM `CertificateFile`, `PrivateKeyFile`, `PrivateKeyPassphrase`, with suffixes selected by HTTP/source/target/web-service variables. Documented SSH/SSL key files are read-only to the Jitterbit user, with accessible directories. **DESIGN:** use Linux absolute paths; managed private files initially 0400 to the verified service account, directories 0700. Validate actual required access before applying permissions. Parse certificates, check expiry and key match. Restrict identity suffixes; reject newline/config injection and symlink targets. Passphrase fields have no confirmed encrypted representation: do not write plaintext passphrases under the current policy.

**VERIFIED — J10:** bundled Java uses `/opt/jitterbit/jre`; documented truststore is `/opt/jitterbit/jre/lib/security/cacerts`, managed by the bundled `keytool`. `/etc/sysconfig/jitterbit` can override `JRE_HOME`; vendor support is for the bundled version. **DESIGN:** inspect the effective JVM and any `javax.net.ssl.trustStore` override. Validate the store format rather than assuming JKS from its filename. Back up, compare alias AND certificate fingerprint, import only missing approved certificates, verify after import, and restart only when changed. Resolve alias collisions explicitly. Never modify the system Java store as a fallback or infer TLS enforcement merely from a successful import.

## Logs and health evidence

**VERIFIED — J11:** `/opt/jitterbit/log/jitterbit-agent.log` is the main log; `Installer.log`, `ProcessEngine.log`, `Scheduler.log` and cleanup/error logs also exist. Native and Docker logs differ.

**VERIFIED — J01:** the documented upgrade synchronization message is:

```text
Agent synchronization for environment <123456> and agent group ID <987654> completed at ...
```

It proves a synchronization event in that documented context, not a universal successful registration or current heartbeat.

**VERIFIED — J12:** troubleshooting documents `java.net.SocketTimeoutException: Read timed out`, `postmaster.pid does not exist`, and database authentication failures. Support tools cover cloud/Apache/Tomcat connectivity and component state. Cloning persisted agent identity can cause collisions. **REQUIRES CONFIRMATION:** exact selected-version registration/authentication/environment/TLS/proxy messages and supported cloud-status query. A database authentication error must not be classified as Harmony authentication failure.

**DESIGN:** use a monotonic bounded timeout (proposed 300 seconds), starting from the current attempt's log inode/offset; handle rotation/truncation and absent logs. Match only reviewed version-specific fixtures and intended identity/group. Check current service state plus current Harmony status; absence of errors is insufficient. Historical success must never pass a new attempt. On a healthy rerun, prefer fresh cloud status rather than forcing restart to generate a success line. Until an authoritative success contract exists, return unverified/timeout, not SUCCESS. Failure patterns are diagnostic evidence, not universal root-cause rules.

**VERIFIED — J13/J16:** required outbound destinations depend on region/features; agents establish outbound HTTPS WebSockets. **DESIGN:** use a reviewed endpoint profile, test DNS/TLS and WebSocket reachability, and distinguish transport access from authentication. No public inbound NSG rule or Application Gateway is needed solely for registration. Workload/API ingress is a separate requirement.
