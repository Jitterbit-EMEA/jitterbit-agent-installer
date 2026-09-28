# Registration strategy

Status: DESIGNED / REQUIRES_TEST. DEP-002 is PARTIALLY_RESOLVED. These are separate adapters; none is implemented. Sources are indexed in [references](references.md), accessed 2026-09-22.

## Documented lifecycle baseline

J04 explicitly applies auto-registration to native Linux: use `/opt/jitterbit/Resources/register.json` after removing old credentials, then restart. Registration produces encrypted `/opt/jitterbit/Resources/credentials.txt`, used for reconnection. The registration file is consumed; the described Docker conf directory cannot contain both files. Verify consumption and collision handling on native 12.10 rather than assuming all Docker details transfer.

J04 states automatic registration cannot use a proxy, without a native-Linux or 12.10 exemption. Treat this as a constraint for this target. Its persistent default is `deregisterAgentOnDrainstop=false`. Native Linux credentials can remain stale after deregistration. Docker 12.4+ container restart re-registration behavior does not establish native behavior.

## Interactive registration

Preserve native `jitterbit-config` prompts and subsequent `jitterbit restart` as an assisted baseline for support, troubleshooting and one-off setup (J01/J03). Manual registration requires a pre-created Console agent in the intended group (J04). Use a dedicated non-production identity. No terminal recording of secret entry. Interactive execution requires a TTY and is rejected by unattended Azure dispatch. The current framework flag still returns NOT_IMPLEMENTED.

## Parameterized jitterbit-config

J03 documents this parameter form (reference syntax only, **forbidden with real secrets in argv**):

```text
jitterbit-config -U USERNAME -P PASSWORD -l REGION_URL -o ORG_NAME -g GROUP_ENVIRONMENT -a AGENT_NAME
```

| Input | Documented option |
| --- | --- |
| Login URL | `-l` / `--login-url` |
| User, password | `-U` / `--user`, `-P` / `--password` |
| Credential input file | `-f` / `--credentials-file` |
| Organization, group, agent | `-o` / `--organization`, `-g` / `--agent-group`, `-a` / `--agent` |
| Reduced prompts | `-q` / `--quiet` is not a full unattended guarantee |
| Database unattended mode | `-u` / `--unattended` still has a database-password caveat; do not equate with proven fresh-install automation |

Group representation is group name plus environment name separated by underscore (J03); verify exact selection and collisions, do not guess from a display label. All registration identifiers and authentication input must be supplied for a deterministic invocation; database prerequisites must be separately qualified. The credentials-file format, secure stdin input, native environment-variable input, exact persisted outputs and log redaction are not established by the public utility reference. Inspect supplied package scripts/help and obtain vendor clarification before implementing Mode B. Do not assume this input file equals product `credentials.txt`.

Plaintext password arguments are visible to sufficiently privileged process observers; typing literal secrets also risks shell history. SDK/subprocess argument arrays avoid shell injection but do not hide argv. No automatic fallback to `-P`. J08 separately documents `--proxy-host HOST[:PORT]`, `--proxy-user`, `--proxy-password`, `--proxy-ntlm-domain`. A secure proxy-password channel remains required. Keep certificate verification enabled. Mode B is the candidate for proxy-dependent automation once its secret channel is proven.

## Automatic register.json

For a fresh no-proxy target, select a version-qualified token adapter. Target cloud URL, numeric group ID and naming prefix must be explicit; the group already exists but automatic registration creates the agent entry. Design order: stop/hold newly installed services as qualified, reconcile identity, retrieve secret, create the registration input, start once, poll, verify consumption and cloud identity. Do not delete an existing identity just to enable this path.

Vendor fields include `cloudUrl`, `agentGroupId`, `agentNamePrefix`, `token` or encrypted `username`/`password`, `deregisterAgentOnDrainstop`, `retryCount`, `retryIntervalSeconds` (J04). Native environment input using Docker's `AUTO_REGISTER_TOKEN` is not an approved adapter. Public docs describe native applicability and the shared token field, but do not prove this exact 12.10 package: **REQUIRES_TEST**.

## Authentication comparison

| Authentication | Evidence and decision |
| --- | --- |
| Plain username/password | Manual utility supports it; command-line secrets forbidden. Assisted prompt behavior must be checked for echo/logging |
| Encrypted username/password | J04 uses `jitterbit-utils -e USERNAME PASSWORD`; current docs describe Linux utility packaging but exact 12.10 binary is uninspected. Encryption invocation exposes plaintext argv. Key Vault retrieval does not fix this. Do not run that flow automatically or reimplement vendor encryption |
| Agent Registration token | J05 provides Admin-created, environment-scoped tokens under Management Console > Access Tokens > Add token. Select Agent Registration, not Agent Metric; avoid All Environments. Preferred no-proxy candidate, subject to security/lifecycle tests |

J05 exposes Active/Inactive controls and deletion. It does not document an expiry/TTL, one-use guarantee, or the exact effect of revocation on already registered agents/reconnects. Do not call these short-lived tokens. Obtain a test token directly into Key Vault through approved administrative handling; record rotation owner and test invalidation/new registration/reconnect separately. No token value is requested in chat. Token preference reduces username/password distribution but still creates a bearer-secret exposure boundary.

## Proxy compatibility

Design validation must reject automatic registration when the agent needs a proxy, before secrets or package mutation. A download-only proxy is a distinct transport setting and must not be confused with the Harmony proxy requirement. For required Harmony proxy, use the assisted baseline or a qualified Mode B adapter; until secure inputs and trust setup are confirmed, unattended provisioning is BLOCKED. Never bypass TLS verification or silently switch modes. The automatic-mode constraint comes from J04; J08 provides the manual proxy route.

## Persistent Azure VM recommendation

Recommend no-proxy auto-register/token, persistent identity, deregistration disabled, conditional on tests and transient-file policy. Reboot, service restart and VM stop/start must reuse the same identity; fresh VM recreation receives a new identity unless an explicitly reviewed migration transfers exclusive ownership.

| Existing state | Required reconciliation policy (design) |
| --- | --- |
| Fresh install, no credentials | Permit selected registration after all gates |
| Same installation and intended identity | Preserve credentials, check fresh health, no registration/restart merely to create logs |
| Existing credentials but uncertain identity | Stop with LIFECYCLE_ACTION_REQUIRED; do not inspect secret contents in diagnostics |
| Deregistered/stale identity | Separate approved recovery; stop service, establish old identity disposition, remove only validated stale material, then fresh registration |
| Both input and credentials exist | Stop and reconcile; never choose one blindly |
| Clone/snapshot/golden image | Exclude credentials and registration material; do not boot two copies with the same identity |

J12 documents collisions after cloning registered hosts. For migration, inventory identity and registration state outside secret contents, drain/shut down the original host, and confirm vendor-supported recovery. Ordinary cleanup must not remove valid product credentials or uninstall a partially installed agent. Backups/snapshots of registered disks are sensitive and cannot serve as general images.

## credentials.txt ownership and persistence

Purpose/encryption/restart preservation are documented in J04. A portable numeric owner/group/mode is not. Inspect package control scripts, installed metadata and actual service identity on the test VM. Require service access and minimum privileges; proposed private mode 0600 to the verified account is a policy target, not a verified vendor requirement. Never recursively chmod/chown the installation. Preserve on ordinary restart/rerun; exclude from source, diagnostic bundles and reusable images. Removal after confirmed deregistration is an explicit recovery step, not general idempotency.

## Secret lifecycle and register.json security

Design flow: VM Managed Identity obtains Key Vault access in process → pinned secret version into memory → approved registration adapter → product-managed identity → temporary cleanup. Azure authentication tokens and Harmony tokens must not enter AI/orchestration payloads.

| Location | Classification | Required handling |
| --- | --- | --- |
| Key Vault | ALLOWED | Dedicated environment boundary; least privilege; rotation owner |
| Installer/provider memory | ALLOWED | Short lifetime, opaque wrapper/redaction; avoid dumps; reference clearing is not guaranteed zeroization |
| Process arguments, shell history | FORBIDDEN | Secret references only; no secret interpolation or encryption command with real argv |
| Azure public/protected settings, custom data, ordinary Blob config, Git | FORBIDDEN for secret values | Non-secret locators/digests only; protected settings still do not prevent guest leakage |
| stdout/stderr/framework and debug logs | FORBIDDEN | Fixed events, no raw provider/vendor output, no shell tracing |
| Environment variables | AVOID | No native adapter approved; inherited environments/process inspection remain exposure paths |
| Temporary disk files | FORBIDDEN under existing no-plaintext-persistence policy | No silent exception for mode 0600 |
| Transient register.json | AVOID / conditional ALLOWED | File-based bearer secret remains plaintext. Memory-backed delivery requires explicit policy acceptance and product tests before use |
| credentials.txt | PRODUCT_MANAGED | Persistent encrypted identity, verified ownership, backups controlled, contents excluded |

Proposed file adapter: retrieve secrets only after preflight; use umask 077, safe path components and exclusive no-follow creation; verify parent ownership and no symlink race; determine service user before setting owner; write JSON in-process without shell, never print it. If memory-backed delivery is approved, validate an isolated file/bind-mount approach at the required path without moving the entire Resources directory to volatile storage. Do not assume symlinks are accepted. Account for swap, crash dumps and snapshots; tmpfs alone is not a universal no-persistence guarantee.

Record only existence/owner/group/mode/mtime. On success verify Jitterbit consumed the input. On failure/timeout first stop only the new registration attempt and ensure it cannot keep reading/retrying, then remove owned transient input and copies; do not remove unrelated credentials. SIGTERM cleanup and next-run residue detection are required; SIGKILL/power loss cannot promise finally-block cleanup. Failed cleanup is an explicit failure requiring action. Secure erasure is not guaranteed on SSD/COW storage. This unresolved storage policy is a Phase 2 prerequisite.

## Ephemeral future use

VMSS, containers and Kubernetes are DEFERRED. They need per-instance identity, bounded scale-out registration, drain handling, secret rotation and orphan reconciliation. Do not apply Docker's restart semantics to native VMSS. A deregister-on-stop model changes identity guarantees and is a separate adapter/profile, never the persistent-server default.
