# Interactive TranDb reads

The read path uses one pinned SSH invocation. It starts a short-lived Python process through existing non-interactive sudo, sends a bounded collector bundle on standard input, verifies its SHA-256 before executing any collector, queries local TranDb through the existing provider, and returns JSON. No collector files or bytecode are staged on the PA; no services, listeners, connection pools or persistent SSH sessions are created. Lifecycle behavior is unchanged.

## Choose only the work needed

Run from the checkout with the customer's existing protected inventory:

```bash
.venv/bin/python scripts/management/capture-trandb.py \
  --inventory /private/inventory.json --target qa-vm --mode running --limit 100
```

Without `--output`, bounded results go directly to stdout for a single-call interaction. For large captures or retained evidence, add `--output /private/new-capture.json`; this preserves the previous summary-to-stdout behavior and exclusively creates the capture with mode 0600. Existing files and symlinks are rejected. Output paths under this checkout's `output/` remain ignored by Git.

| Mode | Work and interpretation |
| --- | --- |
| `running` | One query: raw status 3 only |
| `active` | One query: submitted, pending, running, cancel-requested and received (0,1,3,8,10) |
| `errors` | One query: error, success-with-child-error and SOAP fault (7,9,11); preserve these distinct raw statuses |
| `definitions` | One query: bounded operation definitions and project/environment metadata |
| `backlog` | Two queries: incoming requests and log synchronization backlog |
| `identity` | One query: explicitly whitelisted agent identity fields |
| `reporting` | All original 25 reports, including relationship/grain/metadata diagnostics |
| `profile` | Existing full schema/row-count research; intentionally heavier |

The existing default mode (`profile`) and limit (500) are retained for compatibility. Interactive callers should explicitly select a focused mode and typically use a limit of 100. The reporting limit remains 1–2000; reaching the limit flags potentially truncated reports. No query text, arbitrary predicates or filesystem paths are accepted as database-selection arguments. There is no result cache: every read is live, and every source timestamp/coverage limit still matters.

`errors` lists execution metadata, not secret-bearing connector payloads or unrestricted error text. Detailed errors, lineage and SFTP correlation retain their existing bounded assessment workflow. `backlog` is not a full health or capacity assessment. None of these modes executes a customer operation.

## Shared implementation and compatibility

- `scripts/management/trandb_reporting.py` owns the original query catalogue and focused selections. The original 25 SQL strings are unchanged and covered by a compatibility digest test.
- `tools/handoff/readonly_capture.py` builds and verifies the in-memory collector bundle and measures collection time.
- `capture-trandb.py` retains full reporting/profile captures and adds focused modes and optional stdout results. The workload capture/comparison and offline operation-assessment tools still consume the same report families. Added `mode`/`timings` fields are additive.
- The existing local provider still reads database credentials only on the PA. Every query uses explicit `BEGIN READ ONLY`, a five-second statement timeout, a one-second lock timeout and `ROLLBACK`; unsupported PgBouncer startup `PGOPTIONS` remain stripped. Query failures remain UNAVAILABLE/null with explicit failure metadata, never empty-success results. Remote stderr/private errors are withheld.
- SSH retains the selected private-key path, IdentitiesOnly, BatchMode, StrictHostKeyChecking, pinned known_hosts, connection timeout and output bound. Optional stdin is capped; collector input is capped more tightly at 256 KiB and output remains capped at 1 MiB. SHA-256 establishes transfer integrity for trusted checkout code; it is not a code signature or authorization for arbitrary supplied code. No approval or credential scope is expanded.

For this release the collector uses the existing RC9 runtime location, as the previous path did. It requires that established QA runtime and sudo access; it does not silently install dependencies or accept a changed host key. The fixed lifecycle candidate and its package integrity are unaffected.

## Measured improvement — 15 October 2026

Same QA target and installed 12.11.3.2 agent, same client, limit 100, three sequential samples per path. Baseline source is commit `39f89b0`; final raw captures stay local. Timings cover CLI launch through private capture write, including SSH/network. They exclude AI reasoning, tool scheduling and UI rendering. This is a small-history QA measurement, not a production performance SLA or peak-load benchmark.

| Read | Before median | After median | Scope |
| --- | ---: | ---: | --- |
| Complete reporting | 18.180 s | 2.978 s | Same 25 SQL reports; 83.6% reduction, about 6.1× faster |
| Running operations | Previously required full capture/filtering | 2.341 s | New one-query mode; no equivalent focused baseline existed |

Baseline reporting samples: 19.044, 18.180, 18.101 seconds. Refactored reporting samples: 3.305, 2.978, 2.871 seconds. Database query medians were 168 ms before and 159 ms after; the gain came primarily from replacing eight SSH/SCP invocations and temporary staging with one execution, not changing SQL. The refactored path uses one invocation. The focused running response was 969 bytes on this idle sample; it is not a result-size promise for busy workloads.

The portable [benchmark summary](../evidence/read-path/benchmark-2026-10-15.json) records the samples and validation limits. Full captures contain dynamic database counters, so do not require every value across separate snapshots to be identical; stable identity/definition comparisons and unchanged query contracts establish compatibility.

## Repeat the benchmark

```bash
.venv/bin/python scripts/management/benchmark-read-path.py \
  --inventory /private/inventory.json --target qa-vm \
  --output output/read-benchmark/new-run --samples 3 --limit 100
```

The command runs reporting and running reads by default, runs reporting then running within each sample loop, and stores private raw captures plus a private summary. `--modes` can select other read modes; `profile` is an explicit heavier choice. It requires a new directory, reports failures explicitly and does not execute operations. For a new before/after comparison, run it from each trusted revision against the same target and record workload/versions. The original `39f89b0` baseline used the old capture command wrapped with the same CLI-through-file wall-clock measurement, since that revision predates this benchmark helper.

Timing fields distinguish client preparation, remote collector elapsed time, aggregate query time, SSH round-trip and total collection time. `sshAndStartupOverheadMs` is round-trip minus remote collector time: network, SSH/interpreter startup and return transfer combined, not a separately measured network-only latency. `totalMs` excludes subsequent local file serialization; benchmark `elapsedMs` includes it. Per-query timings include psql startup/connection and JSON parsing, not just server execution plans. No persistent database connection refactor was needed for this gain.

Live validation also passed active, errors, definitions, backlog and identity modes, plus the original 164-query schema profile. Stable agent identity/operation definitions and all 25 SQL strings matched the baseline. These facts and per-mode timings are in the benchmark summary.

Final validation: 509 unit tests and four additional offline operation-assessment checks pass. Both skills validate; targeted lint and whitespace checks pass. The final primary benchmark was repeated after response-validation changes; the evidence also retains preliminary samples.

## Local evidence retention after cleanup

The 15 October cleanup removed preliminary benchmark captures and the original raw before samples after their timings, source revision and compatibility findings had been recorded in the portable evidence summary. Final `after-final/` captures, baseline timing summary and mode-validation summary remain local. Historical before/after database-row comparisons cannot be replayed from removed raw samples; their recorded findings remain evidence, not a currently replayable dataset. The current benchmark command remains executable. See `docs/maintenance/cleanup-2026-10-15.json` for removal roots and retained artifacts.
