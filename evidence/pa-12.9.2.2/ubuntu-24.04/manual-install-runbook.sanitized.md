# Sanitized manual install evidence

Source Reference 1 SHA-256: `f7ae02d5404ee634fa57cbf53689a74ba88af668d25807fc6367545497d21ac5`.

Observed on Ubuntu 24.04.5 LTS amd64 with PA 12.9.2.2:

1. Package indexes were refreshed and `odbcinst`, `unixodbc` and `unzip` were installed. No general OS upgrade is part of the contract.
2. `jitterbit-agent_12.9.2.2_amd64.deb` was downloaded from the vendor host. The path-bearing URL is omitted because no durable provenance or digest was supplied.
3. The package was installed with `dpkg --install`. Initial messages that services could not start without agent credentials were observed and are expected before registration.
4. Product paths appeared under `/opt/jitterbit`, including the bundled JRE, Resources, PostgreSQL data and logs.
5. A manual credential-based registration run reached Harmony login, Agent Services, synchronization and `All services are running`.

This reference establishes package/runtime layout and local services. Reference 2 is the native automatic-registration evidence used by the adapter.
