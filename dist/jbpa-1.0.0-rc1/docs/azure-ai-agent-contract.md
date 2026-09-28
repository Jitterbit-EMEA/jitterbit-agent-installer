# Azure AI Agent execution contract

The external controller provisions the VM and its Managed Identity, configures Key Vault secret-read RBAC and egress, selects an independently approved framework archive/hash, and supplies target VM, operation, desired PA logical version, config reference, secret references and artifact policy. It must not pass token values through command-line arguments or Azure public settings.

| Operation | JBPA command | Required boundary |
| --- | --- | --- |
| INSTALL | `jbpa install --config PATH --version VERSION --non-interactive` | Production artifact approval; QA additionally explicit controlled-test |
| UNINSTALL | `jbpa uninstall --complete` | Explicit complete local removal; force only by separate explicit flag |
| HEALTH | `jbpa health --profile PROFILE` | Expected IDs; steady state also expected names/version; restart requires since-utc |
| DIAGNOSTICS | `jbpa diagnostics` | Read-only; unknown probes remain null |
| ENTERPRISE_CONFIGURE | `jbpa enterprise --config PATH` | Existing qualified tuple and branch-specific health/identity arguments |
| ARTIFACT_INSPECT | `jbpa artifact inspect --version VERSION` | Network and dpkg-deb; no install |
| ARTIFACT_VERIFY | `jbpa artifact verify --version VERSION` | Exact metadata and governed digest; no install |
| REGRESSION | `jbpa regression run --version VERSION --config PATH --live` | Disposable clean VM; BASIC default; full-lifecycle explicit |

Consume process exit code and the single JSON envelope. `status=SUCCESS` with exit 0 means the requested action completed; inspect `state` and `details.status` to distinguish a dry-run plan, no-change, local-only health and full completion. INSTALL success requires `details.status=COMPLETE`, serviceRunning and harmonyRegistered true. Bare local health does not satisfy a composite HEALTH operation. Never determine success by parsing Installer.log, jitterbit-agent.log, or human text. Failures have a stable category, detailed error code and retryable flag. The controller must not blindly retry registration, drain, or package mutation.

The RC result schema is `config/schemas/rc-result.schema.json` version 1.0. It contains versions, artifact, platform, registration, health, enterpriseConfiguration and error; historical results remain nested under details. Legacy standalone utilities keep their prior schemas. Config is version 1, catalogue version 2, runtime contract and artifact manifest 1.0. Breaking schema changes require a bump and caller migration.

`azure/custom-script/release-bootstrap.sh` accepts an HTTPS URL or local archive, independently expected SHA-256, guest config path and private result path. It validates the digest, bounds and checks tar members, creates an isolated Python venv, installs pinned runtime requirements using the guest's approved package index, verifies release file hashes/catalogue/contracts, then invokes JBPA. Python 3.10+ and venv support must already exist. Internet/private-index access for Python dependencies is a deployment prerequisite; the bundle does not promise offline setup. Private Blob artifact retrieval for PA remains in the existing Managed Identity provider; the minimal framework URL downloader does not acquire Blob authorization.

Framework locations are `/opt/jbpa`, `/etc/jbpa`, `/var/lib/jbpa`, `/var/log/jbpa`, `/var/cache/jbpa/artifacts`; product ownership remains under `/opt/jitterbit`. Result parent directories must already be private and owned by the executing account. Existing results cannot be overwritten. The wrapper refuses an existing release destination; choose the installed release directly for retries instead of recreating it.

This phase supplies and verifies the handoff contract. It does not modify the separately authored Azure provisioning agent or claim live CSE dispatch. Production artifact provenance, Python dependency supply-chain approval, release signing, VM sizing and security approval remain governance gates.
