# Native Linux PA lifecycle

The `bin/jbpa` entrypoint exposes `install`, `validate`, `health`, `diagnostics`, and `uninstall`. Install delegates to the qualified bootstrap; validate and diagnostics retain their read-only framework semantics; health reports only local service status and does not claim Harmony confirmation. `bin/jbpa uninstall --complete` performs local decommission. `bin/jbpa-pending-operations` is the read-only TranDb operation monitor.

Complete uninstall preserves the JBPA framework and removes only the Jitterbit product. It first requests drain-pause, waits for the live active-operation count to reach zero, requests drain-stop, waits for all product processes to exit, then removes and purges the package, removes the `jitterbit` account, clears residual product state, and verifies the host is clean. `--force` permits a recorded hard stop only after the graceful drain or stop timeout; it is never implicit. A failed operation query blocks uninstall.

The locally registered agent uses `deregisterAgentOnDrainstop=false`. Local uninstall therefore does not claim to delete the Harmony agent record. `--remove-harmony-agent` records `HARMONY_AGENT_REMOVAL_REQUIRED`; no undocumented Harmony API or console automation is used. The expected Harmony state is stopped or existing until an approved cleanup mechanism is used.

This Phase 2D workflow is qualified only for native PA 12.10.1.1 on Ubuntu 24.04.5 amd64. Ubuntu 22.04, other PA builds, containers, proxies and non-root installations require separate evidence. See the [runbook](runbooks/native-linux-pa-uninstall.md).

## Phase 2E clean reinstall regression

The same QA VM was verified clean after Phase 2D, then PA 12.10.1.1 was reinstalled through the existing unattended path. The tested local sequence is **install → auto-register → healthy → drain-pause → active-operation poll → drain-stop → complete uninstall → clean host → reinstall → fresh auto-registration → synchronized → healthy**. Package, product tree, account, credentials and local services were recreated. The new login marker reports Agent ID 646830; the old ID was not retained in sanitized evidence, so exact distinctness remains unverified. The old Harmony record was not deleted or inspected. The new agent was left installed and healthy. See the Phase 2E summary (source repository).

A clean reinstall now fails before registration if credentials reappear immediately after package installation (`STALE_CREDENTIALS_REINTRODUCED`). The local full lifecycle is `TESTED_LIVE`; exact old/new Harmony numeric ID comparison remains `UNVERIFIED` as a separate evidence gate.

## Enterprise configuration boundary

`jbpa enterprise --config <validated-config>` evaluates optional branches independently. All disabled is a no-change result. Phase 2F.1B qualified real truststore explicit endpoint import and matching-alias idempotency on PA 12.10.1.1 / Ubuntu 24.04.5 amd64: new backup, fingerprint/hash change, one restart, mandatory fresh health, then NO_CHANGE with stable hash and zero restart. The branch remains isolated from install/uninstall. Existing-agent sync and service-status observations are supporting; initial-registration synchronization remains mandatory and unchanged. Steady-state preflight and idempotency require current identity, credentials, product connectivity and core services without a new restart. SSH, SSL and proxy remain fail-closed and deferred. See the [health contract](health-contract.md) and Phase 2F summary (source repository).

## Phase 2G release candidate

The coherent CLI adds version/artifact/regression commands and a stable RC result envelope. Existing install/registration/drain/uninstall/reinstall workflows are delegated, with catalogue and latest qualification guards before installation. Latest installation carries one inspected file through the workflow and retains exact hash verification. Basic regression is explicit live, requires a clean target and leaves the agent; full-lifecycle is separately selected. No batch historical install or automatic Harmony cleanup exists. Configured uninstall timeouts require --config; explicit command flags take precedence.
