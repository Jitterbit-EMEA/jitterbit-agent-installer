# Phase 2C Summary

## Status

**COMPLETE for the controlled Ubuntu 24.04 functional regression.** One primary automated PA 12.10.1.1 run completed on 2026-09-25 without manual repair or a second restart. Ubuntu 22.04 and production sizing remain untested.

## Test Environment

The VM was `JBLAB-PA-AUTOMATION` on Ubuntu 24.04.5 LTS, kernel `6.17.0-1022-azure`, amd64, 2 vCPU and 7,882 MiB RAM. Its Azure managed OS disk was expanded from 30 to 64 GiB before the primary run; the later continuation brief's 32-GB starting point no longer reflected the VM state. Ubuntu expanded `/dev/sda1` and its ext4 root filesystem to 65,445,814,272 bytes. `QA_SIZING_EXCEPTION=APPROVED` applies to the 2-vCPU functional test; `productionSizingValidated=false`. The controlled preflight returned `PASS_WITH_TEST_EXCEPTION`, with no disk or memory exception. See [preflight](../evidence/pa-12.10.1.1/ubuntu-24.04/preflight.yaml).

## Cleanup

PA 12.9.2.2 was in `deinstall ok config-files` state. Its remaining 552-MB product tree included `Resources/credentials.txt`; `register.json` was absent. Metadata was captured without file contents, then the package config was purged and the stale tree removed on the disposable VM. `CLEAN_BASELINE=PASS` before installation. See [pre-cleanup](../evidence/pa-12.10.1.1/ubuntu-24.04/pre-cleanup.yaml) and [post-cleanup](../evidence/pa-12.10.1.1/ubuntu-24.04/post-cleanup.yaml).

## Artifact and Dependencies

`jitterbit-agent_12.10.1.1_amd64.deb` identified as `jitterbit-agent`, version `12.10.1.1`, amd64, with `odbcinst` and `unixodbc` dependencies. The VM rechecked SHA-256 `604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8` immediately before installation. Integrity is `LOCALLY_CALCULATED`, approval `APPROVED_FOR_TEST_ONLY`. The workflow refreshed APT indexes and installed `odbcinst`, `unixodbc`, and `unzip` before `dpkg`; no OS upgrade or fix-broken repair ran. Dependency metadata matches the 12.9 baseline.

## Installation and Runtime Paths

The workflow used `silent_install=1 dpkg --install`; `dpkg` finished with `install ok installed` for 12.10.1.1. Installation took 52 seconds by dpkg log timestamps. The product installed at `/opt/jitterbit`, with `Resources`, a bundled JRE, `jre/bin/keytool`, `jre/lib/security/cacerts`, `log/Installer.log`, and `log/jitterbit-agent.log` present. The [sanitized installer record](../evidence/pa-12.10.1.1/ubuntu-24.04/logs/Installer.sanitized.log) retains only non-secret metadata; raw logs were not copied. Six installer-log lines contained `error`, but the package installed and subsequent registration and health gates passed. The bootstrap did not retain sanitized `dpkg` stdout/stderr, so those streams are an evidence gap.

## Registration and Local Health

The VM Managed Identity re-read and validated all seven JBLAB Key Vault fields after disk resizing without outputting secret values. The bootstrap created a valid `register.json` through its `jitterbit:jitterbit` mode-`0600` writer, issued one restart, then observed automatic registration start and completion, new credentials, Harmony authentication, Agent Services connection, request flow, synchronization, and heartbeat. After success, `register.json` was absent; `credentials.txt` was `jitterbit:jitterbit`, mode `0640`. The transient registration-file metadata was enforced by code but was not independently sampled during the live run. All four local services were running; see the [structured result](../evidence/pa-12.10.1.1/ubuntu-24.04/installation-result.json), [lifecycle](../evidence/pa-12.10.1.1/ubuntu-24.04/register-lifecycle.md), and [service status](../evidence/pa-12.10.1.1/ubuntu-24.04/local-service-status.txt).

## Timing and Contract Comparison

The log appeared 55.0 seconds after the restart. Automatic registration completed around 57 seconds after restart; Harmony login around 59 seconds; Agent Services around 61 seconds; synchronization around 173 seconds. The measured runtime poll was 175.3 seconds and total provisioning 268 seconds. The package was pre-staged, so download duration was not measured. See [timing](../evidence/pa-12.10.1.1/ubuntu-24.04/timing.yaml).

Classification: **CONTRACT_COMPATIBLE_MINOR_CHANGES**. Required package, registration, Harmony, synchronization, path and service behavior stayed compatible with PA 12.9.2.2. The new timing observations do not establish a performance comparison. See the [regression comparison](regressions/pa-12.10.1.1-vs-12.9.2.2.md).

## Production Gates

GATE-01 through GATE-05 and GATE-07 remain PASS for their stated implementation scopes. GATE-06 remains test-only because the digest lacks independent trusted verification. GATE-08, GATE-09, GATE-11 and GATE-12 are PASS for this controlled Ubuntu 24.04 no-proxy token-registration tuple. GATE-10 remains PENDING for Ubuntu 22.04. Production sizing is not validated. See [readiness gates](production-readiness.md).

## Tests and Remaining Work

The suite passed 125 tests with zero failures, including a new fixture based on sanitized actual PA 12.10 markers and checks that only the exact 2-vCPU controlled exception can proceed. Ruff, yamllint, schema/example/Markdown-link checks, and the bounded credential scan passed. ShellCheck and shfmt were unavailable. The next separate regression is PA 12.10.1.1 on Ubuntu 22.04; production artifact integrity approval and production sizing validation remain separate work.
