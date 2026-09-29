# Jitterbit Private Agent Automation

For a customer installing on an existing VM, start with [Install a Private Agent: the short path](docs/customer-start-here.md). RC6 adds one guided launcher, `sudo ./bin/jbpa-customer`, for setup, credentials, versions, install, upgrade and status. The [detailed customer runbook](docs/customer-install-runbook.md) remains available for review and recovery. For engineers integrating a separately built infrastructure AI or Claude Code project, see the Claude Code / external AI operating kit (source repository); its handoff commands still target the historical RC3 release. JBPA begins only after the VM is provisioned.

JBPA is a native Linux Private Agent lifecycle framework with version-aware artifact inspection, Azure Managed Identity / Key Vault or protected local-file registration, health profiles, graceful local uninstall and enterprise truststore configuration. The canonical framework version is in `lib/jbpa/__init__.py`. This release candidate is for controlled qualification; it is not production approved. The local-file credential path passed a live interactive PA 12.10.1.1 installation on Ubuntu 24.04 on 2026-09-28; see the customer runbook report (source repository).

## Current qualification

| Capability | Evidence boundary |
| --- | --- |
| PA 12.10 / package 12.10.1.1 | TESTED_LIVE on Ubuntu 24.04.5 amd64: install, registration, health, drain, complete local uninstall and reinstall |
| PA 12.9 / package 12.9.2.2 | Scoped live installation / registration / initial health evidence; no full lifecycle claim |
| PA 12.8 through 11.47 | 17 pinned releases AVAILABLE_UNQUALIFIED |
| Ubuntu 22.04 | NOT YET LIVE-TESTED |
| Production sizing | NOT VALIDATED; the live functional VM used an explicit 2-vCPU QA exception |
| Java truststore / explicit endpoint trust | TESTED_LIVE for the supplied CA:FALSE certificate; true custom CA NOT_TESTED_WITH_CURRENT_CERTIFICATE |
| SSH/SFTP | DEFERRED_NO_TEST_MATERIAL |
| SSL client certificate | DEFERRED_NO_PRIVATE_KEY_OR_MTLS_ENDPOINT |
| Proxy | DEFERRED_NO_PROXY_TEST_ENVIRONMENT |
| Harmony-side record deletion | NOT AUTOMATED / PENDING |
| Production artifact promotion | GOVERNANCE REQUIRED; the PA 12.10 digest is LOCALLY_CALCULATED |

See the [version matrix](docs/version-qualification-matrix.md), [readiness matrix](docs/production-readiness.md) and preserved [phase reports](docs/README.md).

## Setup and CLI

Use Python 3.10 or newer. On supported Ubuntu, install Python venv support and the Debian tools before framework setup. A release bundle contains pinned Python requirements; it does not contain an interpreter or dependency wheels. Install dependencies from your approved package index before invoking JBPA.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
bin/jbpa version
bin/jbpa version resolve recommended
bin/jbpa version resolve 12.10.1.1
bin/jbpa artifact list
bin/jbpa artifact inspect --version latest
bin/jbpa artifact verify --version 12.10
# Optional: verify retained bytes without another network request
bin/jbpa artifact verify --version 12.10 --file /var/cache/jbpa/artifacts/PACKAGE-HASH.deb
bin/jbpa artifact intake --version 12.8
```

Plain `version` and `artifact list` are offline. `latest` is the mutable vendor endpoint, never a static alias. Only explicit resolution downloads it. `recommended`, `latest-tested` and `latest-available-pinned` initially point to logical 12.10. Artifact inspection invokes `dpkg-deb --field`; it never executes package scripts. Redirects are restricted to HTTPS on the two configured Jitterbit hosts, with no embedded credentials. Other CDN destinations fail closed pending policy review.

```bash
bin/jbpa install --config /etc/jbpa/agent.yaml --version recommended --non-interactive
bin/jbpa install --config /etc/jbpa/agent.yaml --version latest --controlled-test --non-interactive
bin/jbpa uninstall --complete
bin/jbpa health
bin/jbpa diagnostics
bin/jbpa validate --config /etc/jbpa/agent.yaml
bin/jbpa enterprise --config /etc/jbpa/agent.yaml --dry-run
```

Production install remains blocked by current artifact approval. The QA example additionally requires `--controlled-test`. Unqualified version/platform combinations fail with `VERSION_NOT_QUALIFIED` (or `LATEST_VERSION_NOT_QUALIFIED`). An explicit `--allow-unqualified --controlled-test` classifies the attempt as `EXPERIMENTAL_VERSION_TEST`; it does not establish support or approval. Hardware, secrets, platform and existing-product-state gates still apply.

For composite existing-agent health, use `health --profile STEADY_STATE_EXISTING_AGENT` with the expected identity arguments described in the [health runbook](docs/runbooks/health.md). Bare `health` is explicitly LOCAL_ONLY and cannot confirm Harmony identity. Restart profiles require a UTC event boundary. Initial-registration synchronization remains mandatory. Existing-agent synchronization and Support Tools service-status are supplementary.

## Version onboarding and regression

Add the exact logical/package identity and URL to the governed catalogue, inspect and save metadata, review provenance, then run an explicitly authorized disposable-host regression. Compatible observed contracts do not require lifecycle source changes. Contract changes require a version-specific adapter and review; they must not redefine the proven baseline globally.

```bash
bin/jbpa regression run --version 12.8 --target ubuntu-24.04 --mode basic \
  --config /etc/jbpa/agent.yaml --live --allow-unqualified
# Destructive extended qualification requires an explicit mode:
bin/jbpa regression run --version 12.8 --target ubuntu-24.04 --mode full-lifecycle \
  --config /etc/jbpa/agent.yaml --live --allow-unqualified
```

BASIC requires a clean host and leaves the installed agent. FULL_LIFECYCLE additionally drains, uninstalls, verifies clean state and reinstalls. Neither mode deletes Harmony records or automatically promotes qualification. A metadata-only historical batch is available through `artifact intake --all-unqualified`; it is serial and deletes each temporary package before moving on. It is not part of validation, build, or normal startup.

## Release and Azure integration

```bash
scripts/validate.sh
scripts/build-release.sh
scripts/verify-release.sh dist/jbpa-1.0.0-rc6.tar.gz
```

Build runs source validation, tests, lint, formatting, schemas, catalogue/contracts, and a bounded credential scan. It emits a clean framework directory, manifest, file hashes, archive and archive digest. Verify with an independently supplied expected archive digest for deployment; the colocated sidecar alone is not independent provenance.

The framework uses `/opt/jbpa`, configuration `/etc/jbpa`, state `/var/lib/jbpa`, logs `/var/log/jbpa` and optional artifact cache `/var/cache/jbpa/artifacts`. Jitterbit retains `/opt/jitterbit`. Cache identity includes exact package version and SHA-256. Latest install keeps one inspected package for the run and the native installer rechecks its hash and fields before installation.

Use the [Azure AI Agent contract](docs/azure-ai-agent-contract.md) and `azure/custom-script/release-bootstrap.sh`. The external controller consumes exit code plus structured JSON, not raw product logs. The RC envelope is version 1.0; legacy operation results remain under `details`. Existing standalone utilities retain their historical result formats.

See [configuration](docs/configuration.md), [security review](docs/security-review.md), and [runbooks](docs/README.md). No tokens, passwords, registration files, private keys, QA logs, evidence corpus or PA packages belong in a release bundle.

RC2 adds explicit bootstrap qualification override forwarding. The seventh positional bootstrap argument is `false` by default; `true` is accepted only with `controlled-test`. It forwards `--allow-unqualified` without changing artifact, platform, configuration, registration or health checks. See [bootstrap usage](docs/azure-bootstrap.md) and [release notes](docs/release-notes.md). Ubuntu 22.04 live qualification remains pending.

## External orchestrator handoff

JBPA does not provision VMs. It starts at an already provisioned host and manages PA install, configuration, registration, health and removal. The external tool owns infrastructure, access, identity and delivery. See the [canonical contract](docs/external-orchestrator-contract.md), [host prerequisites](docs/pre-provisioned-host-contract.md) and LOCAL handoff harness (source repository). No subscription, resource group, VNet, subnet, region or VM SKU is required for PA installation.

The historical `azure/provisioning` and `bin/jbpa-azure` remain NON_PRODUCTION / DEVELOPMENT_TEST_HARNESS / NOT_PART_OF_JBPA_RUNTIME. They are excluded from RC2 and are not a required JBPA integration architecture. Historical deployment evidence (source repository) is retained.

## RC3 runtime completeness

RC3 adds first-class `jbpa reinstall --config PATH --version VERSION --non-interactive` and shared structured readiness through `jbpa validate --config PATH`. See [preflight](docs/preflight-contract.md), [reinstall](docs/runbooks/reinstall.md) and Phase 3C (source repository). Runtime implementation is mock/local tested; live Ubuntu 22.04 and external handoff gates remain pending. RC2 is immutable historical evidence.

## RC4 local-file credentials

RC4 adds a non-Azure `local-file` secret provider. Each config reference names one root-owned, mode `0600` file in a root-only directory, and the runtime validates those files before using their values. Use the [local-file example](config/examples/local-file-qa.example.yaml) and [customer VM quickstart](docs/customer-quickstart.md). RC3 remains immutable historical evidence.

## RC5 customer lifecycle

RC5 adds `jbpa versions`, guided `install --interactive`, and a guarded in-place `upgrade` command. Interactive install pins the exact artifact before operator confirmation; upgrade preserves the agent installation and registration. See the [customer VM quickstart](docs/customer-quickstart.md). RC4 remains immutable historical evidence.

## RC6 guided customer launcher

RC6 packages `bin/jbpa-customer`, a standard-library launcher that prepares its Python runtime, prompts for protected Harmony files, lists catalogue versions, runs preflight and delegates install/upgrade/status to JBPA. See [the short path](docs/customer-start-here.md). This launcher does not expand enterprise SSH, SSL or proxy support. RC5 remains the live-tested local-file installation baseline; RC6 still requires its own live qualification.
