# External handoff test harness

NON_PRODUCTION external caller tooling, NOT_PART_OF_JBPA_RUNTIME. No infrastructure provisioning and no Jitterbit lifecycle or vendor-log interpretation. Canonical boundary: [external orchestrator contract](../../docs/external-orchestrator-contract.md).

LOCAL executes a preinstalled, already delivered RC2 or RC3 on the same host; it verifies the approved archive SHA and every installed runtime manifest file before dispatch, captures process exit and retrieves the new schema-valid result. Configuration and private result parent directory must already exist. Existing result files are rejected. The host/runtime must be trusted and files immutable to untrusted writers during verification/execution. This is not a sandbox against a privileged malicious host.

```bash
bin/jbpa-handoff --request /path/to/handoff.json \
  --binary /opt/jbpa/jbpa-1.0.0-rc2/bin/jbpa \
  --release /path/to/jbpa-1.0.0-rc2.tar.gz \
  --sha256 68fa05cc43577a15f948c81a6e56e8d2b725d66d969934ec3f2eb6316e3266da
```

Use actual installed binary path. The bootstrap's release root may differ from this example. Invoke with approved root/sudo for mutations; this tool never escalates automatically. CI's remote mock exercises the same execute/retrieve interface without contacting any host; it does not prove delivery, remote integrity or live qualification.

The separate `jbpa-handoff-ssh` caller supports RC3 controlled INSTALL and REINSTALL on an already-provisioned Ubuntu 22.04 amd64 host. It requires approved SSH access, a pinned host key, passwordless `sudo -n`, Python 3.10+, a configured package index for the RC3 Python dependencies, and an agent configuration containing secret references rather than secret values. The caller verifies the RC3 archive hash locally, delivers it to a private guest stage, verifies it again on the guest before extraction, and checks installed manifest files. It invokes the canonical `validate` profile before exactly one JBPA lifecycle command, retrieves the fresh structured result and consumes its generic status. It does not inspect vendor logs. The guest setup step installs the JBPA Python environment; it does not install the Private Agent.

Use a distinct request and result path for each operation, and preserve INSTALL evidence before invoking REINSTALL. The request `target` must equal the SSH host. Example shape (replace placeholders with approved local paths and host details):

```bash
bin/jbpa-handoff-ssh \
  --request /path/to/install-request.json \
  --release dist/jbpa-1.0.0-rc3.tar.gz \
  --config-source /path/to/agent-secret-references.yaml \
  --user approved-user --key /path/to/private-key \
  --known-hosts /path/to/pinned-known-hosts \
  --evidence-dir evidence/phase-3d/ubuntu-22.04
```

For REINSTALL, use the matching request with `operation=REINSTALL`, a new `resultPath`, and omit `--config-source`; the guest release and retained archive are reverified. The caller refuses the wrong OS, architecture, or starting host state before invoking either lifecycle operation. A failed invocation still requires operator review of its structured evidence and host state before any retry. Host-access data and secret values must never be committed.

REINSTALL is supported by RC3 and explicitly unsupported in RC2. The caller invokes one product command; it does not compose uninstall/install. ENTERPRISE_CONFIGURE requires expectedIdentity with agentId, agentGroupId, agentName and agentGroupName; argv maps these to the existing enterprise health arguments. No result or contract test closes a production gate without the separately controlled live caller.
