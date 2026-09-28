# Jitterbit Private Agent Automation

JBPA is a native Linux Private Agent lifecycle framework with version-aware artifact inspection, Managed Identity / Key Vault registration, health profiles, graceful local uninstall and enterprise truststore configuration. The canonical framework version is in `lib/jbpa/__init__.py`. This release candidate is for controlled qualification; it is not production approved.

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
scripts/verify-release.sh dist/jbpa-1.0.0-rc1.tar.gz
```

Build runs source validation, tests, lint, formatting, schemas, catalogue/contracts, and a bounded credential scan. It emits a clean framework directory, manifest, file hashes, archive and archive digest. Verify with an independently supplied expected archive digest for deployment; the colocated sidecar alone is not independent provenance.

The framework uses `/opt/jbpa`, configuration `/etc/jbpa`, state `/var/lib/jbpa`, logs `/var/log/jbpa` and optional artifact cache `/var/cache/jbpa/artifacts`. Jitterbit retains `/opt/jitterbit`. Cache identity includes exact package version and SHA-256. Latest install keeps one inspected package for the run and the native installer rechecks its hash and fields before installation.

Use the [Azure AI Agent contract](docs/azure-ai-agent-contract.md) and `azure/custom-script/release-bootstrap.sh`. The external controller consumes exit code plus structured JSON, not raw product logs. The RC envelope is version 1.0; legacy operation results remain under `details`. Existing standalone utilities retain their historical result formats.

See [configuration](docs/configuration.md), [security review](docs/security-review.md), and [runbooks](docs/README.md). No tokens, passwords, registration files, private keys, QA logs, evidence corpus or PA packages belong in a release bundle.
