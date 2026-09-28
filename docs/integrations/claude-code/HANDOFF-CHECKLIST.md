# Colleague handoff checklist

**JBPA DOES NOT CREATE VIRTUAL MACHINES.** Check these in the engineer's infrastructure-AI project and on its already-provisioned target.

- [ ] Claude Code is installed and authenticated on the developer/orchestrator environment, not installed on the PA VM merely for JBPA.
- [ ] The infrastructure project has a concise `CLAUDE.md` JBPA boundary section and `.claude/skills/jbpa/SKILL.md`; unrelated instructions remain intact.
- [ ] `/jbpa` is visible and the engineer knows which operation to invoke.
- [ ] The immutable RC3 archive is available; its independently supplied SHA-256 is `4b06e3715cb5faf3472354934fc12c04b54c7febe25d98f47bf1f038075ad90e`.
- [ ] The target Linux VM already exists with suitable OS/architecture, CPU, memory, disk, DNS, time and outbound connectivity.
- [ ] Approved remote execution is configured; where SSH is used, the host key is pinned and automatic trust is disabled.
- [ ] Cloud identity is already attached and permitted to read the required secret references.
- [ ] `agent.yaml` validates against RC3 schema and contains references, not token/password values.
- [ ] The release archive and installed files are verified on the guest before execution.
- [ ] `jbpa validate` returns a passing readiness profile and the expected actual host state.
- [ ] INSTALL/REINSTALL is requested through JBPA only; REINSTALL is one first-class operation.
- [ ] A new private result path is used, and process exit plus result JSON are retrieved.
- [ ] The result validates against schema 1.0; operation/release match; success requires exit 0, SUCCESS status/category and null error.
- [ ] No Jitterbit vendor logs, TranDb, service names or Harmony markers are parsed in the external AI tool.
- [ ] No credentials, private keys, token-bearing registration files or value-bearing live config are committed or pasted into prompts.

The deliverable set for the colleague is RC3 archive/digest, schema-valid agent template, [external handoff contract](JBPA-EXTERNAL-HANDOFF.md), [quickstart](JBPA-QUICKSTART.md), [runbook](JBPA-OPERATOR-RUNBOOK.md), request/result schemas and optionally the [SSH reference caller](../../../tools/handoff/README.md). Historical evidence is not needed for routine integration. This checklist cannot itself close live GATE-10 or GATE-13.
