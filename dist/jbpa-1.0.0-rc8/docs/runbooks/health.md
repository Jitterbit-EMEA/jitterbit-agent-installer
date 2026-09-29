# Health runbook

```bash
jbpa health --profile STEADY_STATE_EXISTING_AGENT \
  --expected-agent-id AGENT_ID --expected-agent-group-id GROUP_ID \
  --expected-agent-name AGENT_NAME --expected-agent-group-name GROUP_NAME \
  --expected-version 12.10.1.1
```

Replace identity placeholders with approved non-secret metadata. The steady gate needs existing credentials, exact current about identity, connection-check and four core services; no new log boundary or restart. For EXISTING_AGENT_RESTART, POST_CONFIGURATION_RESTART or POST_ROLLBACK_RESTART add --since-utc with the actual host event boundary. Rollback also requires --expected-truststore-sha256. Never fabricate a fresh boundary for an old restart. INITIAL_REGISTRATION retains required auto-registration and fresh sync. Existing-agent fresh sync and rowless service-status are supplementary. Bare health reports LOCAL_ONLY and cannot certify Harmony. See [the health contract](../health-contract.md).
