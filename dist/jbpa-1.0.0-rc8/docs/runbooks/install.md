# Install runbook

Provision the configured Ubuntu VM, Python runtime and dependencies, Managed Identity, Key Vault RBAC and egress. Verify the independently approved JBPA archive hash and framework manifest. Put a validated reference-only config at /etc/jbpa/agent.yaml with a private result directory.

```bash
jbpa version resolve recommended
jbpa validate --config /etc/jbpa/agent.yaml
jbpa install --config /etc/jbpa/agent.yaml --version recommended --non-interactive --result-file /var/lib/jbpa/install.json
```

Current production artifact approval is pending, so the production path blocks. For the qualified functional QA tuple, use the QA example and explicitly add --controlled-test. Unqualified versions require --allow-unqualified and remain EXPERIMENTAL_VERSION_TEST. Do not restore old credentials or automatically repair a dirty host. Latest is resolved once to exact bytes/version/hash, then installed from those bytes. Assess exit code, details.status=COMPLETE, serviceRunning and harmonyRegistered; a PLANNED result is not installation evidence. See [the tested native runbook](native-linux-pa-install-tested.md).
