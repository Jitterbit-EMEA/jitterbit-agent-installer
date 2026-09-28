# JBPA integration troubleshooting

**JBPA DOES NOT CREATE VIRTUAL MACHINES.** The external tool prepares the host and transports the verified release. JBPA owns Jitterbit Private Agent diagnosis and lifecycle interpretation. Start with process exit, fresh [schema-valid result](../../../config/schemas/rc-result.schema.json), `category`, `state`, `error.name` and `error.retryable`. Do not grep vendor logs in the caller.

| Scenario | Owner | Safe next action | Do not do |
| --- | --- | --- | --- |
| Host unreachable | External orchestrator | Check approved address, route, firewall, SSH/remote execution and pinned identity. | Treat transport failure as JBPA install failure or retry a mutation blindly. |
| SSH host-key mismatch | External orchestrator | Stop; verify host identity through an independent trusted channel, then update pinned key if legitimately changed. | Enable automatic host-key trust. |
| Release delivery failed | External orchestrator | Check transport, private stage, disk and permissions; verify exact RC3 digest on guest before retry. | Execute partial/unverified content. |
| RC3 archive hash mismatch | External orchestrator | Stop `JBPA_RELEASE_HASH_MISMATCH`; replace from approved immutable source and independently verify. | Change the approved hash to match unknown bytes. |
| Host readiness FAIL | JBPA reports; external tool fixes infrastructure preconditions | Read `details.preflight.checks`, `hostState` and platform; repair the specific prerequisite and revalidate. | Run INSTALL/REINSTALL despite blocking FAIL or UNCONFIRMED. |
| Unsupported OS or architecture | External infrastructure owner | Supply a supported image/architecture; re-run preflight. | Override OS or architecture with `--allow-unqualified`. |
| Package manager busy or repositories unavailable | External infrastructure owner | Wait for legitimate lock/repository recovery, then revalidate and follow `error.retryable`. | Kill package processes or blindly retry INSTALL. |
| Insufficient CPU, memory or disk | External infrastructure owner | Resize/expand through infrastructure workflow, then revalidate. | Treat functional QA CPU exception as production sizing proof. |
| Key Vault/IMDS unavailable or access denied | External identity owner + JBPA validation | Confirm VM Managed Identity, vault URI/access, DNS/TLS and non-secret reference names; rerun preflight. | Put token values in YAML, request JSON or prompts. |
| PA artifact hash/DEB identity mismatch | JBPA | Stop, inspect governed version catalogue and independent artifact provenance. | Override digest or call `dpkg` directly. |
| PA install failed | JBPA | Preserve result and host state; follow `category/state/error.retryable` before any new operation. | Clean `/opt/jitterbit` from caller code. |
| Registration or Harmony authentication failed | JBPA | Preserve sanitized result, verify secret references/network/identity prerequisites, and use JBPA diagnostics. | Read `credentials.txt`, print `register.json`, or parse Harmony markers yourself. |
| Initial synchronization or Agent Services failed | JBPA | Inspect structured health/result and JBPA support evidence; review outbound connectivity. | Mark success from package installation alone or grep vendor logs in caller. |
| Health failed | JBPA | Check selected health profile, observed expected identity and structured health details; rerun only after cause is understood. | Treat plain LOCAL_ONLY health as Harmony confirmation. |
| REINSTALL drain timeout/active operations | JBPA | Preserve drain timeline and result, wait/review operations using JBPA; decide separately whether force is justified. | Call drain-pause/drain-stop, query TranDb or compose uninstall/install in caller. |
| Result file missing | External handoff | Confirm unique path, private parent, permissions, execution completion and retrieval channel; classify `RESULT_FILE_MISSING`. | Infer success from exit/output text alone. |
| Result schema invalid or operation/version mismatch | External handoff | Stop as integration/release compatibility failure; inspect RC3/schema versions and preserve sanitized bytes. | Interpret unknown fields or declare success. |
| JBPA nonzero exit with result | JBPA | Surface result `category`, `state`, `error.name` and retryability; follow the relevant runbook. | Blindly retry a mutating command. |

For an unqualified tuple, `--allow-unqualified` is valid only with `--controlled-test` and explicit controlled-test authorization. It bypasses qualification policy alone. The Ubuntu 22.04/PA 12.10.1.1 live gate and external handoff gate remain pending. The [operator runbook](JBPA-OPERATOR-RUNBOOK.md) gives exact RC3 commands and security handling.
