# Uninstall runbook

```bash
jbpa uninstall --complete --result-file /var/lib/jbpa/uninstall.json
```

This explicitly requests graceful drain-pause, TranDb active-operation polling, drain-stop, core stopped verification, package purge, product account removal, exact residual cleanup and clean-host validation. Query failures and timeouts block. --force is a separate operator decision after a graceful timeout; it is never implied. JBPA state/framework remain intact. Harmony deletion is not automated. Preserve failure results and use a new filename for a retry. See [the native uninstall procedure](native-linux-pa-uninstall.md).
