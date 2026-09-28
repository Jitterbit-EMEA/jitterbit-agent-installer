# Phase 2E Summary

## Status

**The local full lifecycle, reinstall after complete uninstall, and fresh registration are TESTED_LIVE.** The QA VM was left with PA 12.10.1.1 installed, synchronized, and all four local services running. Exact old/new Harmony numeric ID comparison is **UNVERIFIED** because the previous ID was not preserved in the Phase 2C sanitized evidence. The old Harmony record was neither deleted nor inspected; the strict ID-comparison gate is not claimed.

## Starting State

The PA 12.10.1.1 / Ubuntu 24.04.5 amd64 VM had completed graceful drain, local uninstall, clean-host validation, and idempotent repeat. The current [independent clean baseline](../evidence/pa-12.10.1.1/ubuntu-24.04/reinstall/clean-baseline.yaml) found no product package, `/opt/jitterbit`, `jitterbit` user, credentials, registration file, bundled PostgreSQL, product process, command link, or startup integration. VM sizing was 2 vCPU, 7.7 GiB memory and 64 GiB managed OS disk. The 2-vCPU QA exception remains approved; production sizing is unvalidated.

## Clean Host Validation

`CLEAN_REINSTALL_BASELINE=PASS`. No cleanup was performed in Phase 2E. The VM's Managed Identity and access to all seven configured Key Vault fields passed a presence/type check without printing values.

## Artifact Validation

The pre-staged `.deb` was recalculated immediately before installation: SHA-256 `604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8`, exact expected match. Debian metadata identified `jitterbit-agent` 12.10.1.1, amd64, depending on `odbcinst` and `unixodbc`. Integrity is locally calculated and approval remains QA only. See [artifact evidence](../evidence/pa-12.10.1.1/ubuntu-24.04/reinstall/artifact.yaml).

## Dependency Preparation

`odbcinst`, `unixodbc`, and `unzip` were already installed. The existing bootstrap ran its bounded `apt-get update` and `apt-get install` path; no package upgrade or fix-broken repair was requested. `dpkg --audit` was empty before installation.

## Reinstall

The existing controlled-test bootstrap ran once with no manual recovery. `dpkg` recorded package installation from 19:55:29 to 19:56:22 UTC (53 seconds). The [result](../evidence/pa-12.10.1.1/ubuntu-24.04/reinstall/reinstall-result.json) returned `COMPLETE`, no error, `serviceRunning=true`, and `harmonyRegistered=true`. `dpkg-query` confirmed `install ok installed` for 12.10.1.1 amd64.

## Product State Recreation

The reinstall recreated `/opt/jitterbit`, `bin`, `Resources`, `log`, `jre`, and `pgsql`, plus the `jitterbit` account. These had been absent at the clean baseline. [Runtime facts](../evidence/pa-12.10.1.1/ubuntu-24.04/reinstall/runtime-facts.json) contain only non-secret state.

## Fresh Registration State

Credentials were absent on the clean host. A new guard rechecked them after package installation and before registration input creation; it would fail with `STALE_CREDENTIALS_REINTRODUCED` if package scripts created them. The live run passed that guard. No old local credentials or registration input were restored.

## register.json

The bootstrap created a new registration file through the existing hardened `jitterbit:jitterbit` mode-0600 writer, then removed it after successful registration. Creation and final absence are in the result and runtime facts. Its transient ownership/mode were not independently sampled during this run; its contents were never copied.

## New credentials.txt

The new registration generated `/opt/jitterbit/Resources/credentials.txt`. Its existence, `jitterbit:jitterbit` ownership and mode 0640 were independently checked without reading its contents. The exact filesystem creation time was not captured; the first matching runtime log event was 19:57:36 UTC.

## Harmony Authentication

Auto-registration completed at 19:57:36 UTC, followed by successful REST authentication and agent login at 19:57:39 UTC. The new agent ID is **646830**, in group **678370**. These IDs came from the non-secret login marker. A Harmony console status check was not performed.

## Agent Identity Comparison

The previous agent ID and display name are absent from the saved sanitized Phase 2C evidence. This was recorded as `OLD_AGENT_IDENTITY_NOT_AVAILABLE`. A fresh registration from a clean local host was proven, but numerical distinctness from the old Harmony record cannot be verified. No claim is made about the old record's current state. See [identity comparison](../evidence/pa-12.10.1.1/ubuntu-24.04/reinstall/identity-comparison.yaml).

## Agent Services

The agent log recorded Agent Services connection at 19:57:40 UTC and request flow at 19:57:41 UTC.

## Synchronization

The log recorded agent-group synchronization at 19:57:39 UTC. This marker precedes the Agent Services marker in the vendor log; all required markers and health gates were observed. Heartbeat evidence appeared at 19:58:34 UTC.

## Local Health

`jitterbit status` returned exit 0 with ProcessEngine, Scheduler, FileCleanup, VerboseLogShipper and `All services are running`. The new agent remains installed; no uninstall was invoked. See [service status](../evidence/pa-12.10.1.1/ubuntu-24.04/reinstall/local-service-status.txt).

## Runtime Contract Comparison

**REINSTALL_CONTRACT_COMPATIBLE_MINOR_CHANGES.** The same package dependencies, product tree, registration path, credentials path, registration/authentication markers, Agent Services, synchronization and local-service contract passed as in the original Phase 2C install. The reinstall completed registration-to-health faster (115 seconds after restart versus the original longer poll); the marker order and installer error-word count varied. No contract-breaking behavior was observed. Exact old/new identity comparison remains unavailable.

## Timing

The agent log became available 55.007 seconds after the single restart. The bootstrap completed its registration and health polling 115.191 seconds after restart. The exact restart timestamp, dependency duration and total bootstrap-to-health duration were not instrumented; no unsupported timings are inferred. See [timing evidence](../evidence/pa-12.10.1.1/ubuntu-24.04/reinstall/timing.yaml).

## Automated Tests

The full suite passed **143 tests, zero failures**, up from 142. The new test injects credentials from the package step and verifies that registration stops before writing `register.json` or restarting. Ruff, formatting, YAML lint, shell syntax, schema/link checks and bounded credential scan passed. ShellCheck and shfmt were unavailable.

## Production Readiness

Native reinstall after complete local uninstall is `TESTED_LIVE` for PA 12.10.1.1 on Ubuntu 24.04.5 amd64 using the QA sizing exception. Fresh registration, Agent Services, synchronization and local health are also `TESTED_LIVE` for this tuple. Exact identity distinctness and Harmony-side old-record state remain unverified. Production artifact approval, production sizing, Ubuntu 22.04, optional JKS/SSH/SSL/proxy branches and Harmony-side deletion remain pending.

## Remaining Work

Capture the previous Harmony ID from a sanctioned Harmony-side source, if available, and compare it with 646830; do not read deleted credentials or remove the old record as part of this phase. Add exact T0 and milestone timing instrumentation if future runs require precise latency measurements. The current QA agent should remain online.
