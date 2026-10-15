# Mixed workload and SFTP evidence — 12 October 2026

At 09:54:30 UTC (11:54:30 SAST), 79 retained executions were visible: 13 file retrieval successes, 12 validation errors, 12 Slack warning outcomes and 12 Gmail successes. Four run rows remained Running in this snapshot. All 25 reporting queries succeeded. Root execution: `f62599d0-8bff-466a-81d2-1cb6b9bb305d`.

The later file-operation query returned 20 successful retrieval records. Representative retained output:

```text
Operation: File | ERP | Titan | Get File
Operation ID: 18958210
Run GUID: 45069833-3d99-4a7f-8c79-d42511b9e596
Entered: 2026-10-12T09:54:47.456126+00:00
Status: 4 (Success)
The operation "File | ERP | Titan | Get File" completed successfully.
```

This is operation log output, not a protocol-level SFTP trace. No explicit SFTP/JSCH/SSHJ records appeared in the bounded agent log scan or matching TranDb messages. The DataInterchange log-location inspection also found no retained SFTP transfer log. Debug-file metadata in the running snapshot was false. No logging or service configuration was changed.

File retrieval success does not establish the protocol used or the remote server's transfer audit. Validation errors are downstream observations, not evidence of SFTP failure. Completion and complete final counts still require an after-run capture.

Evidence: `output/trandb/mixed-logs-running-2026-10-12.json`, `output/trandb/sftp-running-2026-10-12.json`, `output/trandb/sftp-file-details-2026-10-12.json`, `output/trandb/sftp-transfer-locations-2026-10-12.json`.

## Curl logging configuration applied

At 12:05:06 SAST on 12 October, the customer-authorized change set `[Settings] CurlDebugDir=/opt/jitterbit/log/curl`. The directory is owned by `jitterbit` with mode 0700. Configuration ownership/mode and unrelated settings were preserved. Protected on-host backup: `/var/lib/jbpa/backups/curl-logging-20261012T100506Z/jitterbit.conf`. No restart was performed; runtime trace generation is not yet verified. A fresh transfer is needed to check uptake. Curl logging covers other curl-based protocols too; restrict access and disable the setting after the diagnostic window. Change evidence: `output/trandb/sftp-logging-change-2026-10-12.json`.

## Rerun: traces generated and results separated

Latest substantial root run: `6f1cf181-1712-4021-924b-03d41d755ad7`, entered 12:57:09 SAST. Capture at 12:59:56 SAST shows 122 execution records: 20 successful file retrievals, 20 validation errors, 20 Gmail successes, 20 Slack warning outcomes, 20 alert context steps and 20 alert controller steps, plus two controller records (SuccessWithInfo). This is distinct from the earlier 11:53 run. No lifecycle/service restart was performed by the assistant to obtain the traces.

At 13:00 SAST, curl logging contained 64 files totaling 705087 bytes. Diagnostic text confirms SFTP authentication and connection reuse on port 2022. Some retained text shows `rm command failed: No such file or directory`, followed by upload completion. This may be cleanup before upload; the diagnostic-only export does not establish the exact command target or impact. Trace-file count is not a count of business files; trace GUIDs are not yet proven operation GUIDs.

The sampled CSV errors report unsupported `operationType` values `[]` or `["QCXE"]` on physical line 1, with `Header detected: false`; the validator permits UPSERT or DELETE. Incorrect header/column selection is a hypothesis to investigate, not established by log text alone. Successfully retrieving files does not imply successful business processing.

Sanitized trace text: `output/trandb/sftp-rerun-2026-10-12.sanitized.log`. Structured traces: `output/trandb/sftp-curl-rerun-2026-10-12.json`. Operation results: `output/trandb/mixed-logs-rerun-2026-10-12.json`. Validation samples: `output/trandb/rerun-validation-details-2026-10-12.json`.
