# Runtime logs

The primary runtime log is `/opt/jitterbit/log/jitterbit-agent.log`; installer evidence is in `/opt/jitterbit/log/Installer.log`. The primary log may appear about two minutes after restart, so absence before the deadline is `WAITING_FOR_AGENT_RUNTIME`.

Success is composite. The adapter requires automatic registration completion, credentials creation, successful Harmony response, Agent Services connectivity, request flow, synchronization and healthy local services. Heartbeat is supporting evidence. Generic severity words do not decide the outcome.
