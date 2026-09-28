# Phase 1.5 regression validation

Executed locally on 2026-09-22. macOS development host; Python3.14.7 virtual environment. No Linux VM, PA package, Harmony or Azure runtime test.

| Check | Command / evidence | Result |
| --- | --- | --- |
| Full existing regression | ./scripts/test.sh | PASS:76 tests,0 failures; no tests added/removed |
| Secret leak/redaction cases | SecurityTests and AdditionalBoundaryTests within the full suite | PASS; synthetic secrets only |
| Schemas/example/catalogues | scripts/check_repository.py via lint | PASS: four schema definitions, example and both catalogues |
| Available lint | ./scripts/lint.sh | PASS: Ruff check/format, yamllint, bash syntax, repository checks |
| Optional shell tools | shellcheck / shfmt | SKIPPED: not installed |
| Configuration CLI | jitterbit-agent-validate --config config/agent.example.yaml | VALIDATED/0; result schema PASS |
| Actual-host dry-run | jitterbit-agent-install --config config/agent.example.yaml --dry-run | Expected FAILED/10 UNSUPPORTED_OS; schema PASS, plan emitted |
| Ubuntu fixture dry-run | PreflightCliTests.test_ubuntu_dry_run_blocked | Expected BLOCKED/22 INSTALLER_METADATA_MISSING |
| Diagnostics CLI | jitterbit-agent-diagnostics --config config/agent.example.yaml | DIAGNOSTICS/0; result schema PASS |
| Runtime truthfulness | Assertions against all actual CLI outputs | changed=false; serviceRunning/harmonyRegistered null |
| Repository credential scan | Existing bounded pattern scanner in scripts/check_repository.py | PASS; excludes intentional synthetic test material |
| Dependency consistency | .venv/bin/python -m pip check | PASS: no broken requirements; unwritable pip cache warning is unrelated to dependency consistency |
| Implementation preservation | SHA256 before/after for src/bin/config/tests/scripts | PASS:29 files byte-identical |

Local ignored evidence is under results/phase-1.5: tests.log, lint.log, validate/install/diagnostics JSON and logs, regression.json. Directory mode0700; evidence files0600. These are development-host results, not integration-test evidence. No source/schema/config/test/script was modified, no dpkg command was executed and no secret provider was connected.

All requested Phase 0/1 documents and current source/tests were reviewed. Current vendor evidence and access date are in [references](references.md). Documentation links/fences and bounded credential scan include the new Phase 1.5 files. This scan does not guarantee detection of every possible secret. Live acceptance remains NOT RUN under [integration test plan](integration-test-plan.md).

## Acceptance trace

- [x] Phase 0/1 documents, catalogues, schemas, source and tests reviewed.
- [x] Current official registration, native register.json, parameterized utility, token and proxy evidence reviewed — registration-strategy.md.
- [x] Credential lifecycle, ownership uncertainty and secret flow documented — registration-strategy.md.
- [x] Health hierarchy, Support Tools, log evidence and control-plane investigation documented — health-evidence.md.
- [x] Artifact acquisition, internal Azure store and approval lifecycle designed — artifact-intake.md.
- [x] CSE, cloud-init and both Run Command variants evaluated; typed handoff defined — azure-integration-decision.md.
- [x] Schema proposal and state/error/cleanup implementation specification written — schema-change-proposal.md and phase-2-implementation-spec.md.
- [x] Controlled IT-001–010 plan written — integration-test-plan.md.
- [x] Dependency statuses, discovery questions and implementation matrix reconciled.
- [x] Existing 76 tests, available lint/schema/link checks, dry-run, diagnostics and secret checks pass within stated scope.
- [x] No PA installed, dpkg execution, credential-bearing registration file, Harmony registration or Azure mutation.

Research acceptance is complete; unresolved package/security/runtime questions are explicitly recorded dependencies, not silently accepted product behavior.
