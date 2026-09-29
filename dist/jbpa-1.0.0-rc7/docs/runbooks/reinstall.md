# Standalone reinstall

Use RC3 on an already provisioned Linux host. This operation removes the local PA and installs the requested version from a clean state; it is not an in-place upgrade. JBPA framework and infrastructure remain. Harmony records are not deleted.

```bash
/opt/jbpa/bin/jbpa reinstall --config /etc/jbpa/agent.yaml \
  --version 12.10 --non-interactive --result-file /var/lib/jbpa/new-result.json
# Explicit controlled qualification:
/opt/jbpa/bin/jbpa reinstall --config /etc/jbpa/agent.yaml \
  --version 12.10 --non-interactive --controlled-test --allow-unqualified \
  --result-file /var/lib/jbpa/new-qualification-result.json
# No mutation, secret retrieval or artifact acquisition:
/opt/jbpa/bin/jbpa reinstall --config /etc/jbpa/agent.yaml --dry-run
```

Use the actual installed binary path, root execution and an existing private result directory with a new filename. Target artifact approval and qualification apply before removal. `--allow-unqualified` bypasses only qualification; controlled testing is separately required. Production configuration still cannot use QA artifact exceptions.

Supported starts are installed/registered, installed/unregistered and CLEAN_HOST. Clean start deterministically continues as a fresh install. Partial/unknown installations are rejected. A healthy existing agent is actually reinstalled; the operation is not a no-op.

The operation captures non-secret observed prior version/name/group information from Support Tools when available. Numeric IDs may remain unknown; it never reads credentials contents. It validates host readiness, acquires/validates the target artifact before destruction, and holds the shared host lock across removal and installation. The existing TranDb active-operation provider, drain-pause/poll/drain-stop/core-stop and complete-uninstall implementation are reused. No automatic force applies; `--force` explicitly selects the existing uninstall force policy. Drain failures report REINSTALL_DRAIN_FAILED and stop; no install follows a failed removal. Complete removal is independently re-observed before CLEAN_HOST_CONFIRMED. A dirty final host reports REINSTALL_CLEAN_HOST_FAILED.

The normal installer receives the same pinned artifact bytes, without a second download, and creates fresh local registration. Credentials must be absent before register.json. Existing ownership/mode, single restart, auto-registration, new credentials, Harmony authentication, Agent Services, initial synchronization and core health gates remain unchanged. Required fresh-registration states are verified in the composed result before REINSTALL_COMPLETE.

RC result schema 1.0 is retained. `details.reinstall`, `details.preflight`, `details.uninstallResult`, `details.installResult` and state history provide structured evidence. Failure preserves the last successful state and underlying failure code where applicable. Fresh local registration and numeric Harmony identity difference are separate assertions; numeric difference is not required and is never inferred. Re-running a failed REINSTALL requires inspection of current state; do not blindly retry destructive actions.

Qualification is IMPLEMENTED / MOCK-TESTED only. No live REINSTALL or Ubuntu 22.04 qualification is claimed by this release.
