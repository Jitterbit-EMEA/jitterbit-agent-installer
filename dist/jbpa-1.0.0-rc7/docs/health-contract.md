# Private Agent lifecycle health contract

Phase 2F.1B, PA 12.10.1.1 on Ubuntu 24.04.5 amd64. A fresh synchronization-completed log line is mandatory for initial registration; it is supporting evidence for an existing registered agent's start or restart. Its absence is `FRESH_SYNC_MARKER_NOT_OBSERVED`, not proof that the agent is unsynchronized. AgentSupportTools service-status is supplementary/best effort for existing agents, including configuration and rollback restarts.

| Profile | Fresh synchronization | Other required evidence |
| --- | --- | --- |
| INITIAL_REGISTRATION | Mandatory | Completed auto-registration, credentials, expected Harmony identity/authentication, Agent Services, initial synchronization and local services. The tested native registration implementation is unchanged. |
| STEADY_STATE_EXISTING_AGENT | Not required; no restart | Existing credentials, current connection-check, core services, expected agent/version/group from about |
| EXISTING_AGENT_START | Supporting | Existing credentials, fresh expected Harmony identity/authentication, Agent Services, request flow, connection-check, core services |
| EXISTING_AGENT_RESTART | Supporting | Same existing-agent requirements |
| POST_CONFIGURATION_RESTART | Supporting | Same existing-agent requirements |
| POST_ROLLBACK_RESTART | Supporting | Same existing-agent requirements plus verified original file state |

The composite evaluator in `src/jbpa/restart_health.py` returns the profile, mandatory-signal booleans, optional heartbeat/synchronization observations and a status. Complete required observations produce `HEALTHY` even without a new sync line or service-status rows. Missing mandatory observations produce `UNCONFIRMED`; explicit mandatory failures produce `FAILED`. No observed sync line becomes `SYNC_REQUIRED_AND_UNCONFIRMED` only for a synchronization-required profile. Initial-registration runtime logic remains unchanged.

Restart checks capture the host's UTC start time and log inode/offset immediately before restart. They require newly appended timestamped records at or after that boundary, with rotation/truncation handled through timestamps. Historical identity/authentication/Agent Services lines cannot satisfy a new restart gate. Steady-state preflight and idempotency require no new restart, timestamp or fresh log markers. Existing log observations are labeled supporting history; historical synchronization is not presented as fresh synchronization.

The read-only `jbpa enterprise-health` entrypoint accepts a lifecycle profile, expected agent/group IDs and an optional expected restored-store hash. Restart profiles require `--since-utc`; steady state requires expected agent/group names and version instead. It returns only whitelisted metadata and booleans. The simple `jbpa health` command remains explicitly local-only; it is not this composite qualification gate.

## Supported diagnostics

The provider starts `/opt/jitterbit/AgentSupportTools/run.sh` through Bash from its own directory, supplies one of `about`, `connection-check`, or `service-status` on stdin, then `exit`. It uses no invented launcher flags, JSON options or state-changing commands. Jitterbit documents these [Support Tools commands](https://docs.jitterbit.com/agent/agent-support-tools/). Launcher exit zero cannot establish an inner diagnostic pass.

`connection-check` is mandatory and must explicitly report Harmony gateway, Apache and Tomcat reachability. `jitterbit status` is mandatory for all four core services. `service-status` is supplementary: rows produce `AVAILABLE`, a successful launcher with no rows produces `UNAVAILABLE`, and execution failure produces diagnostic `FAILED`. None of these supplementary outcomes alone changes existing-agent mandatory health. Record launcher exit, row count, a sanitized header and execution context; never retain raw process command lines or credential contents. On this PA 12.10.1.1 / Ubuntu 24.04.5 tuple, the installed tool returns a header with no rows under both root and jitterbit. That runtime limitation can be investigated separately and does not block qualification.

The user-supplied Management Console screenshot (source repository) shows agent 646830 Running. Its capture timestamp is unavailable, so it is labeled manual supporting evidence. The machine result remains `NOT_AUTOMATED`; there is no Console scraping or undocumented API.

## Historical Phase 2F.1A outcome

The corrected read-only evaluation ran on the QA VM. Existing credentials, recovery-restart Harmony identity/authentication, Agent Services, request flow, heartbeat, current product connectivity, core services and exact restored truststore hash passed. However, `service-status` returned a table header with **zero rows**, under root and the product account. Its process exit was zero; the provider correctly reports `supportToolServices=null` and overall `UNCONFIRMED`.

The old sync-only rollback classification was too strict. The previous import is `JKS_IMPORT_MUTATION_VERIFIED`, and original-file restoration is verified. Full corrected rollback health is still unconfirmed for the separate missing service observation. Original Phase 2F.1 results remain unchanged; the appended interpretation (source repository) records this distinction.

At Phase 2F.1A, the mandatory read-only gate did not pass and no new mutation occurred. That historical result is preserved. Phase 2F.1B supersedes the service-status requirement and adds a final interpretation (source repository), with current results in the Phase 2F report (source repository). Do not label the agent unhealthy solely from unavailable supplementary diagnostic observations.

## Phase 2G CLI consolidation

`jbpa health --profile PROFILE` now reaches the same composite evaluator as the historical enterprise-health utility. `health --config PATH` supplies a schema-valid expected_identity and optional profile; explicit arguments override config expectations. Bare health is still LOCAL_ONLY. The RC facade wraps the unchanged evaluator's result in the stable 1.0 envelope and preserves its original data under details. Configuration/parser errors are fixed and do not echo invalid values.
