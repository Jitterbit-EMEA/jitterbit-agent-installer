# JBPA for Claude Code and external infrastructure AI

> **Historical RC3 kit.** The current `/jbpa` skill uses the [RC9 Codex / Claude Code remote workflow](../skills/README.md). The commands and release digest below remain RC3 examples and must not be combined with the RC9 skill or customer archive.

If your infrastructure AI has already provisioned a Linux VM, this directory contains everything required to hand that VM to JBPA for Jitterbit Private Agent setup and lifecycle management.

**JBPA DOES NOT CREATE VIRTUAL MACHINES.** It starts at `VM_ALREADY_PROVISIONED`. Successful INSTALL ends at `JITTERBIT_PRIVATE_AGENT_CONFIGURED_AND_HEALTHY`.

```text
Claude Code / infrastructure AI             JBPA on the existing VM
───────────────────────────────────           ─────────────────────────────
Provision VM, OS, network, identity           Validate host
Establish remote execution                    Resolve and verify PA artifact
Deliver verified RC3 + agent.yaml     ──────► Install, configure, register
                                              Synchronize, health-check
                                              Drain, uninstall, reinstall
Consume process exit + result.json    ◄────── Structured result
```

Your tool gives JBPA an existing Linux host, the verified release, `agent.yaml`, one requested operation and any explicitly authorized qualification flags. JBPA gives back a process exit code and structured result JSON. The external tool does not need to know Jitterbit log markers, service names or TranDb.

Start with the [one-page quickstart](JBPA-QUICKSTART.md), then the [operator runbook](JBPA-OPERATOR-RUNBOOK.md). The [external handoff contract](JBPA-EXTERNAL-HANDOFF.md) defines inputs, outputs and responsibility boundaries. Use [troubleshooting](JBPA-TROUBLESHOOTING.md) and the [handoff checklist](HANDOFF-CHECKLIST.md) while integrating.

For the current skill, use the [RC9 remote workflow](../skills/README.md). The historical [RC3 boundary rule](../../../.claude/rules/jbpa-boundary.md), [example requests and result](examples/), [schema-valid agent templates](../../../examples/agent.install.example.yaml), and [reinstall template](../../../examples/agent.reinstall.example.yaml) remain for teams maintaining RC3 integrations. The [security section](JBPA-OPERATOR-RUNBOOK.md#security-and-support-evidence) applies to every workflow.

## Claude Code on the engineer's machine

For macOS, Linux or WSL, Anthropic's [official setup guide](https://code.claude.com/docs/en/setup) gives:

```bash
curl -fsSL https://claude.ai/install.sh | bash
claude --version
claude doctor
claude
```

Install and authenticate in the development/orchestrator environment, **not** on the managed PA VM. In the infrastructure-AI repository, keep `CLAUDE.md` short and stable, and put the detailed on-demand workflow in `.claude/skills/jbpa/SKILL.md`. From an interactive Claude Code session use `/jbpa install` (or `/jbpa reinstall`, `/jbpa uninstall`, `/jbpa health`, `/jbpa diagnostics`, `/jbpa validate`). [Claude Code's skill format](https://code.claude.com/docs/en/skills) supports the project skill and argument-based invocation. Avoid broad tool permissions and do not make `--dangerously-skip-permissions` the integration mode. This repository does not add permissive shared `.claude/settings.json`; the colleague can merge project settings with their existing policy.

Current immutable release: **JBPA 1.0.0-rc3**, archive `dist/jbpa-1.0.0-rc3.tar.gz`, independently supplied SHA-256 `4b06e3715cb5faf3472354934fc12c04b54c7febe25d98f47bf1f038075ad90e`. Primary development PA target: logical `12.10`, package `12.10.1.1`, amd64. Its SHA-256 `604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8` is **QA_TEST_ONLY / LOCALLY_CALCULATED** and is not production artifact approval. Ubuntu 22.04 live qualification and external handoff gates remain pending.

For the colleague, the minimal package is the RC3 archive and approved digest; the [configuration schema](../../../config/schemas/agent.schema.json) and agent example; the [canonical orchestrator contract](../../external-orchestrator-contract.md); this quickstart/runbook; the [request](../../../tools/handoff/request.schema.json) and [result](../../../config/schemas/rc-result.schema.json) schemas; and, optionally, the [SSH reference implementation](../../../tools/handoff/README.md). Historical phase reports, QA logs and evidence corpus are not required to use JBPA.
