# PA 12.10.1.1 registration input lifecycle

The disposable VM had no `/opt/jitterbit` tree, `credentials.txt`, or `register.json` immediately before the primary run. The controlled bootstrap resolved seven JBLAB Key Vault fields through the VM Managed Identity without printing values. It installed PA 12.10.1.1, atomically wrote `register.json` using the code's `jitterbit:jitterbit` and `0600` contract, validated its JSON shape, and issued one `jitterbit restart`.

The structured result records `REGISTER_JSON_CREATED` and one `AGENT_RESTART_REQUESTED`. The agent log records automatic registration starting at 16:57:31 UTC and completing at 16:57:32 UTC. A new `credentials.txt` appeared at 16:57:32 UTC; after the run it was `jitterbit:jitterbit`, mode `0640`, 216 bytes. `register.json` was absent after the successful run. Its transient owner/mode were enforced by the tested writer but were not independently sampled with `stat` during the live run.

No token, registration document, or credential contents were captured. See [installation result](installation-result.json) and the [sanitized agent milestones](logs/jitterbit-agent.sanitized.log).
