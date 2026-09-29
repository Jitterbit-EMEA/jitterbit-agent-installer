# Diagnostics runbook

```bash
jbpa diagnostics --result-file /var/lib/jbpa/diagnostics.json
```

Collect host OS/kernel/architecture, framework/package versions, credentials existence, whitelisted about identity, connection-check, core-service boolean, active operation count, catalogue/artifact status and current health profile. Null means unavailable; do not infer zero or healthy. The command does not return credential contents or raw process/log output. It does not replace a composite health gate.
