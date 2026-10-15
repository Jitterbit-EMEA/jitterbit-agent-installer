---
name: jbpa
description: Set up or manage Jitterbit Private Agents on named, already-provisioned Ubuntu QA VMs. Gather SSH and Harmony settings, clone JBPA, prepare protected credentials, then handle install, upgrade, uninstall, health, status or versions. Also assess operation outcomes, execution lineage and SFTP log evidence through bounded read-only QA collectors.
---

# Jitterbit Private Agent setup and management

Use this skill for conversational onboarding and subsequent PA lifecycle requests. The engineer's computer runs the SSH caller; the VM runs JBPA. This skill does not provision infrastructure. Handle one named target and operation at a time.

The pinned remote caller supports RC9 controlled QA on Ubuntu 24.04 amd64. Read `docs/customer-start-here.md` in the checkout for release limitations. Installing the skill does not transfer another engineer's hosts, keys, credentials or QA approvals.

## First-run setup

A request such as “Set up JBPA on my VM” authorizes preparing the framework and protected credentials. It does not itself authorize installing a PA. If setup accompanies an explicit install request, continue that installation after setup succeeds.

1. Gather missing non-secret information before cloning. Reuse the conversation, a user-selected private inventory, or `$HOME/jbpa-vms.json`. Ask in one concise message for:
   - Target name, reachable public hostname/IP or private address, SSH username.
   - Absolute local SSH private-key path and pinned `known_hosts` path.
   - Harmony cloud URL, numeric agent group ID, and desired agent name prefix.
   - PA version only if installation or upgrade was requested and no version was given.

   Offer defaults and examples in the initial question, and let the user accept them together or override individual fields:

   | Setting | Suggested default or example |
   |---|---|
   | Target name | `qa-vm` (choose another if already used) |
   | Host | User's actual hostname/IP; example `203.0.113.10` is illustrative only |
   | SSH username | `azureuser` for Azure Ubuntu, `ubuntu` for AWS Ubuntu; ask for other images |
   | SSH key | An existing user-selected key; suggest `~/.ssh/id_ed25519` only if it exists |
   | Known hosts | `~/.ssh/known_hosts`; verify this target is pinned |
   | Harmony URL | Offer `https://emea-west.jitterbit.com` for EMEA; request their actual cloud URL for other regions |
   | Group ID | Required actual ID from Harmony; `12345` is an example, never an automatic default |
   | Agent prefix | `qa-agent` |
   | Inventory | `~/jbpa-vms.json` |
   | Local checkout | `~/.local/share/jbpa/repo` |

   Do not silently use an example address, group ID, region or missing key. Ask the user to accept applicable suggestions; already-established values take priority. No token default is allowed.

   Tell the user that the registration token will be entered later in a hidden terminal prompt. Never request private-key contents, registration tokens or passwords in chat. If they already have a protected credentials JSON on the VM, ask for its absolute path instead of asking them to re-enter Harmony settings.
2. Check local SSH files without displaying private-key contents. Expand `~` to absolute paths. If the host key is not pinned, help obtain the expected fingerprint from an authenticated cloud console or VM administrator. `ssh-keyscan` produces only a candidate; compare it with that independent fingerprint before pinning. Never auto-accept a new or changed host key. Test SSH with BatchMode, IdentitiesOnly and StrictHostKeyChecking enabled, a bounded connection timeout, the chosen key and known-hosts file; read the hostname and check `sudo -n true`.
3. Find an existing JBPA checkout containing `bin/jbpa-remote`. If absent, clone `https://github.com/Jitterbit-EMEA/jitterbit-agent-installer.git` into the user's chosen directory, defaulting to `$HOME/.local/share/jbpa/repo`. Clone only into an absent directory. Reuse an existing checkout without resetting files or silently pulling over local work. Record its commit and pinned release. Use subprocess arguments or properly quoted values. Read `docs/integrations/skills/README.md` for the SSH inventory schema and setup helper.
4. Save a mode-`0600` private inventory outside Git, default `$HOME/jbpa-vms.json`, following `config/examples/remote-inventory.example.json` and `config/schemas/remote-inventory.schema.json`. Store named targets with host, user, identityFile and knownHostsFile. Preserve other targets; resolve a conflicting target name before replacing it. Do not store token values, key contents or QA approvals. Include credentialsFile only when a protected source JSON is already staged on the VM.
5. Prepare JBPA and Harmony credentials. For a new target without staged credentials, run the prepared command for the user. On macOS, execute the helper with `--open-terminal`: it launches the actual setup in Terminal and brings the window forward. The user only enters the token in its hidden prompt. The agent may launch this command from a captured session because the launcher itself never asks for or receives the token. Never supply hidden token input through chat or a tool call. On other systems use an available user-controlled terminal launcher; if unavailable, provide the exact command without `--open-terminal` and explain that terminal launching is unavailable.

   ```bash
   python3 /path/to/jbpa/scripts/onboard-target.py --open-terminal \
     --inventory /private/path/jbpa-vms.json --target qa-vm \
     --cloud-url https://emea-west.jitterbit.com --group-id 12345 \
     --name-prefix customer-pa
   ```

   The helper prompts for the token with echo disabled, verifies and delivers the pinned release, installs JBPA's Python dependencies, imports credentials into root-only `/etc/jbpa/credentials.json`, creates `/etc/jbpa/agent.yaml`, cleans temporary credential files and preserves the inventory's other hosts. It installs the framework, not the PA. A non-terminal invocation fails before asking for a token. Existing configuration is never overwritten: inspect and reuse a configured target, or obtain explicit reconfiguration instructions. If the user supplies a staged JSON instead, use the checkout's verified delivery and customer configure/import path with that remote file; never retrieve its contents into chat. Keep credential staging private and clean up only setup-owned files.
6. `TERMINAL_STARTED` means the window was launched, not that setup succeeded. Confirm the terminal helper returned `status=SUCCESS`, or independently verify setup when the user reports completion: check release integrity, runtime dependencies and protected credential/configuration metadata without printing secrets. Do not call an uncompleted hidden prompt successful. Report the checkout, inventory and target names. For setup-only requests stop at “Ready for install, upgrade and health requests.” Resume an already-authorized PA operation; never invent an initial version or auto-install during setup.

The hidden-token step is the user's only secret entry; the skill collects the remaining settings conversationally. No pre-created credentials file is required for this setup route. If an installed copy of the skill predates the setup helper, update the checkout before invoking it, with attention to local work.

## Subsequent operations

Reuse the saved checkout and inventory. Ask which target when ambiguous; prompt only for missing or invalid details. Natural requests include “Install 12.10 on qa-vm”, “Upgrade qa-vm to latest”, and “Check qa-vm health”. The user's requested mutation is its authorization; carry forward explicit approvals in this conversation, but never infer approvals from a saved inventory.

Run from the checkout:

```bash
./bin/jbpa-remote install --inventory /private/path/jbpa-vms.json --target qa-vm --version 12.10
./bin/jbpa-remote upgrade --inventory /private/path/jbpa-vms.json --target qa-vm --version latest
./bin/jbpa-remote status --inventory /private/path/jbpa-vms.json --target qa-vm
./bin/jbpa-remote health --inventory /private/path/jbpa-vms.json --target qa-vm
```

Use the same command shape for versions or uninstall. Setup saves imported credentials on the VM; omit credentialsFile after a successful import to avoid trying to import it again. `latest` is mutable: select it only when requested, then record its resolved version and digest. A catalogue entry does not establish production qualification.

For full health, the VM configuration must contain an independently checked expected identity. After initial installation, capture the observed agent ID/name/group/version through diagnostics and sanitized runtime identity evidence, compare the group and name prefix with the supplied Harmony settings, and configure the health expected identity without exposing credentials. Do not claim full health from the status command alone. If expected identity cannot be established, report diagnostic results and the precise evidence gap.

Success requires exit 0 and status=SUCCESS; installation additionally requires registration and running services. Preserve the private on-VM resultPath and report target, operation, resolved version, outcome and any reason. On release mismatch, missing result, host-access failure or partial installation, inspect host state before retrying. Do not turn a failed install into automatic reinstall or delete Harmony records. Uninstall is local; fresh registration can consume another Harmony group slot.


## Vendor-owned upgrades and requested downgrade recovery

Read `docs/vendor-owned-upgrades.md` for this lifecycle mode. JBPA triggers the normal vendor upgrade installer and monitors its outcome; verification must not restart services, disable vendor autostart, re-expand applications, change permissions or overwrite vendor-restored configuration. Require application readiness as well as services/identity; failed readiness is a failed upgrade, not permission to repair automatically.

Handle an explicitly requested downgrade through complete uninstall/fresh reinstall at the requested release, not an unqualified in-place package/TranDb downgrade. Use `./bin/jbpa-remote reinstall --inventory <private-file> --target <named-target> --version 12.9` for the example recovery route. Pin/qualify the artifact and resource preflight before removal; preserve requested evidence because uninstall removes local history. Reuse protected registration inputs, verify fresh identity/synchronization, and report possible Harmony slot consumption. Do not delete cloud records or perform the subsequent upgrade until authorized. A resource exception for 12.10 does not automatically apply to 12.9. Production security controls remain deferred until explicitly requested.

The 15 October fixed-path QA upgrade is recorded in `docs/upgrade-12.11.3.2-qa-validation.md` and `evidence/pa-12.11.3.2/fixed-upgrade-2026-10-15.json`. It validates one named-host 12.9.2.2 to 12.11.3.2 upgrade; it does not promote catalogue qualification, recommended aliases or production approval. Resource exceptions bind exact host/package and controlled-QA scope; previous-version approval is insufficient.

For upgrade verification, compare baseline and final agent/group identity, exact installed package, operation definitions, deployment error state and backlog as well as fresh runtime and Axis/WSDL readiness. Report component readiness separately from a new cloud deployment, OAuth token-invalidation test or business-operation canary. HTTP 405 with an expected Allow header proves route presence only. Unavailable supplementary service-status parsing stays explicit; native vendor status can provide independent service evidence. After independent identity/version confirmation, refresh JBPA expected-health metadata with a protected backup, without changing vendor configuration. Use the facade's `diagnostics` and `validate` commands for direct on-host inspection; `jbpa-remote status` maps to diagnostics, while on-host `status`/`preflight` are not facade commands.

## Operation and transfer-log assessment

Use this mode for requests about operation outcomes, child failures, backlog or SFTP diagnostics on the named QA target. Read `docs/trandb/operation-assessment-api.md` for the query plan/interpretation and `docs/trandb/knowledge-catalogue.json` for qualified schema/status evidence, from the same checkout used by the caller. The assessment API/MCP action is a proposed UPG-001 service; do not claim it is deployed. If these research resources are absent in a pinned customer checkout, report that version gap rather than invent queries.

1. Resolve target, environment and one root execution or bounded UTC window. For repeated runs, list candidates and select the intended root; do not combine them. Reuse protected inventory and existing SSH. Read-only assessment does not authorize enabling debug logs, restarting services, deployment or repair.
2. Capture bounded reporting with `scripts/management/capture-trandb.py --mode reporting`; use `docs/trandb/operation-assessment.sql` for root-scoped totals and the fixed reporting library for definition, lineage, message metadata, summaries, progress, file counters and current backlog. Credentials remain local. Use explicit read-only transactions/local timeouts through PgBouncer. Do not accept arbitrary SQL or unrestricted filesystem paths from an AI request.
3. Assess saved reporting with `scripts/management/assess-trandb.py --reporting <capture> --root-run-id <guid> --output <new-file>`; optionally provide `--transfer <filtered-curl-capture>`. This is an offline status/lineage summary, not a deployed service or full business-role classifier. Read the resulting coverage/warnings before concluding health.
4. Report root and descendant outcomes separately. A successful controller with failed validation children is not a successful business process. Preserve raw status codes, qualify normalization, keep warnings distinct, and show active/unknown states. Missing/failed/truncated data is not zero or healthy. Aggregate different table grains before joining. `status_ts` is not a proven finish-time column. Root-scoped execution counts, operation attempts, trace files and unique business files are different counts.
5. For native curl-based SFTP diagnostics, check `[Settings] CurlDebugDir`, the actual configured directory and its retained interval. An empty setting explains absent protocol traces, not absent transfers. Return only bounded redacted diagnostic TEXT; curl headers and DATA blocks may contain credentials/payloads. Do not dump `register.json`, connection properties or secret-bearing configuration. A trace filename GUID is not proven to be an operation GUID; correlation is exact, inferred or unmatched with explicit evidence.
6. Interpret event sequences with operation outcomes. Authentication/connection reuse indicates protocol activity. A missing-file `rm` message can be cleanup before upload and is not independently proof of transfer failure. CSV validation is separate from retrieval. The QA rerun observed 20 successful retrievals and 20 validation errors, with unsupported operationType arrays and header detection false; wrong header/column selection remained a hypothesis rather than a confirmed script defect.
7. For MCP delivery use the proposed `pa_assess_operations` contract in `docs/trandb/operation-assessment-contract.json`: MCP/APIM/Studio forwards canonical filters to the management assessment coordinator, which selects fixed read-only providers over SSH and returns findings/stage outcomes/coverage/evidence plus drill-down IDs. Use `pa_list_operation_runs` to disambiguate and detail/log actions to investigate. No extra PA service or JBMQ dispatch layer is needed for these reads. Implement/qualify runtime authorization, deadlines, pagination, role mappings, redaction and load limits before offering this as production monitoring.

Treat the catalogue's dates/VM identifiers and workload examples as evidence, not customer defaults. Record new observed facts and unresolved interpretations in the repository catalogue when asked; preserve historical captures and exclude secrets.


## Estate-wide expert health

For CPU/memory/storage, Apache/JVM/Tomcat, agent services, database pressure, operation backlog/errors or fleet capacity requests, read `docs/estate-health.md` and `docs/estate-health-contract.json` from the current checkout. Use `scripts/management/estate-health.py collect --inventory <private-file> --output <new-directory>` for authorized targets (or repeat `--target`), and `assess --bundle <directory> --output <new-file>` to replay offline. Sampling is read-only, bounded and installs no PA daemon/listener. Existing loopback Apache/JMX endpoints are optional profile inputs; do not deploy the RATP instrumentation script automatically.

Reconcile the expected Harmony/PAG roster and canonical identities before claiming all-agent coverage. Current CLI inventory alone does not verify the cloud roster. Unreachable/uninstrumented/unsupported agents and unavailable/failed providers stay explicit. Check per-source timestamps and historical scope; a completed assessment is not a healthy estate. Separate business/connector errors from resource pressure, and do not infer finish times from status_ts.

Capacity advice requires representative peak history, SLOs, sustained pressure plus backlog, peer utilization, routing/parallelism and downstream/DB/N-1 headroom. Idle peers suggest routing/serialization investigation before adding agents. A short idle/busy sample or CSV validation errors cannot justify an exact VM size/agent count. Return measured evidence, conditional recommendations and missing evidence. Remediation requires its own authorized action. Proposed estate_assess_health/estate_get_health_assessment API/MCP actions use the management durable read-work model; runtime deployment and historical Grafana adapter remain unimplemented.


No-port runtime visibility is documented in `docs/noport-runtime-visibility.md`. Discover existing localhost-restricted Apache status on its existing listener. For an explicitly authorized local-runtime diagnostic profile, use a management-side pinned `localJvmProbeArtifact`/SHA-256: the collector stages the bounded helper per check and removes the stage afterwards. It reads heap/GC/thread/Tomcat counters through the private HotSpot UNIX attach channel without new TCP/UDP ports, daemons, remote JMX, restart, GC or class transformation. The helper class can remain loaded until normal JVM shutdown; do not claim complete removal from JVM memory. The bundled Java 25/native 12.10 QA pairing is verified; unsupported versions/namespaces/loading policies fail closed. Do not enable security flags to force attachment. Keep heavier support-tool launchers outside the measured load window and confirm actual workload activity before attributing performance to a claimed load.
