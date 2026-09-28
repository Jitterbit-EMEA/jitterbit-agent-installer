# Developer guide

> Phase 1.5 addendum (2026-09-22): historical Phase 0/1 content below is preserved. Current readiness and reconciled decisions are in the [Phase 1.5 summary](phase-1.5-summary.md), [dependency register](dependencies.md) and [Phase 2 specification](phase-2-implementation-spec.md). Runtime code/schemas remain Phase 1.

## Scope and layout

The framework is read-only except for explicit new result artifacts. All Phase 2+ mutation/provider execution is disabled. `bin/` contains thin Bash launchers; `src/jbpa/` contains configuration, catalogue, platform, preflight, security, state/results, errors, CLI and provider contracts. `config/` holds reviewed data and strict JSON Schemas. `tests/unit/` contains deterministic tests, `tests/fixtures/` OS files, and `tests/mocks/` the only secret implementation. `scripts/` contains validation entry points.

See [ADR-001](adr/ADR-001-runtime-language.md). Python >=3.10 is chosen for safe structured data and testing; two runtime packages (PyYAML/jsonschema) plus pinned transitives, standard-library unittest, Ruff and yamllint for development. Shellcheck/shfmt are optional host tools. Setup instructions are in [README](../README.md). The dependency set was exercised on the local interpreter recorded in the phase summary; Ubuntu execution is not implied.

## Configuration flow

`load_yaml` bounds input size, uses SafeLoader, rejects duplicate/non-string keys, anchors/aliases and unsafe YAML tags. JSON Schema rejects unknown fields at every defined object layer, enforces scalar types, enums, bounds and conditional feature fields. Semantic checks reject path traversal, controls, URL credentials/query strings, duplicate identities and inconsistent registration/proxy fields. Validation errors never include input values.

Precedence is CLI version > allowlisted JITTERBIT_AGENT_VERSION > config. The config must first be structurally valid. No general environment expansion, arbitrary command substitution or `.env` sourcing. Exact version values and approved aliases are supported; unrecognized aliases fail. All enabled optional features require their inputs, but valid input does not mean their runtime adapter exists.

The Phase 0 `java_trust` name is retained rather than adding a duplicate `truststore` alias. Secret references are `{provider: azure-key-vault, reference: example-name, version: optional-version}`. The global provider metadata selects the vault/identity later; no values are fetched in this phase. Plaintext credential fields and insecure providers are rejected. Null vendor context is a valid development placeholder with blocked runtime readiness, not an approved production config.

Phase 1 adds `logging.level` and `execution.dry_run`. `output.result_path` and `output.log_path` remain reserved metadata and cause no writes; explicit `--result-file` is the only supported artifact sink. Pass a new filename under an existing private, owned directory. No state resume or system logging is implemented yet.

## Catalogue and platform

`config/versions.yaml` is the single release catalogue. Exact release, OS version, architecture and package kind select an artifact. Known, supported-for-target, download-configured (URL plus exact build), integrity-configured, approved and installable are independent result fields. `installable` is always false while executable installer profiles are absent. A configured URL does not establish integrity or runtime support.

To add a release: record evidence IDs, exact build/URL/trusted SHA-256 and reviewed compatibility; extend the support matrix only with evidence, add fixture tests and keep runtime validation `not_run` until real tests pass. Set an alias only to an approved catalogue entry; never scrape latest or auto-promote. Current aliases are empty. Future syntax/build incompatibility requires a new reviewed adapter, not a catalogue workaround.

`os-support.yaml` currently contains only the user-selected Ubuntu 22.04 x86_64 / 12.10 combination. Generic documented support is not real-VM qualification. Numeric minimums use decimal bytes for the documented 8 GB/50 GB, not an invented free-space threshold. OS ID/version and architecture are exact; normalization only maps known synonyms. Recognizing a package family does not grant vendor support. Missing/invalid os-release produces UNKNOWN; an empty policy gives NOT_CONFIGURED; explicit mismatches are UNSUPPORTED.

## Preflight and CLI semantics

Checks carry id, name, status, severity, message and optional dependency ID. Config/catalogue, Linux, expected target, documented CPU/memory/disk capacity, hostname and package-manager executable availability are local checks. Disk available is reported, but the installer free-space requirement is unresolved. DNS/TLS, package repository/lock status, clock validation, port conflicts, product-state inspection, certificates and keys are explicitly not performed. No fabricated endpoint or registration check is present.

`validate` success means the config and selected target policy validate. It does not fail solely because the development host is not Linux; the observed host checks still report FAIL. `diagnostics` success means observations were collected, not that the agent is healthy. `install --dry-run` rejects fatal local incompatibilities before reporting runtime blockers. Warnings alone are not failures. Missing metadata returns BLOCKED/22; configured metadata still cannot bypass provider/evidence blockers (24). Non-dry execution returns NOT_IMPLEMENTED/23 after preflight; interactive mode returns 23 without prompting.

The initial state sequence is INITIALIZED → CONFIG_LOADED → CONFIG_VALIDATED → VERSION_RESOLVED → PLATFORM_DETECTED → PREFLIGHT_COMPLETE, then VALIDATED/DIAGNOSTICS/BLOCKED or FAILED. Reserved installation states cannot be entered. Every result emits state history and an injected-testable run ID/time. No persisted state is trusted or resumed. Unknown installed version, service state and Harmony registration are null, and changed is always false. The result schema prohibits invented runtime success. See [errors](errors.md) for named errors, numeric codes and retryability. Multiple error names can share a process category; inspect `error.name` for precision.

## Secret and output boundaries

A Secret object has redacted str/repr and explicit reveal/clear. The mock resolver registers values with the central Redactor before returning. Production providers must follow that lifecycle before handling any response; never log raw response bodies or exceptions. Secret clearing drops references; Python cannot guarantee physical zeroization of immutable strings, and the redaction registry retains protected values for the invocation to catch late output. There is no claim of a secure memory enclave.

Logger accepts fixed event names/components and restricted fields, with structured JSON on stderr. Only framework-generated check names and plan steps enter descriptions. Resolved values, nested sensitive fields, private-key blocks and credential URLs are redacted. Do not add free-form vendor output to the logger. Arbitrary transformed/encoded secrets cannot be detected universally: prevention through fixed output contracts and no provider payload logging is essential. The final result is allowlisted, sanitized and schema checked; input/exception content is never echoed on parse failure.

The repository scanner is a bounded pattern check, not a full security audit. Synthetic adversarial test strings are deliberately excluded from credential-pattern findings. Test execution separately proves those strings do not escape stdout/stderr or result objects.

## Provider interfaces and future mutation

InstallerProvider defines metadata/download/verify/install/installed_version. RegistrationProvider defines register/verify/classify_failure. HealthProvider takes identity and deadline. SecretProvider defines resolve/clear; ArtifactProvider defines obtain. No runtime implementations or dynamic command-string loading exist. Mocks are outside src and are not selected through user config.

Future mutation must implement MutationProvider read → backup → diff → apply → validate → restore, preserve unrelated content, avoid duplicate keys, and use atomic writes and restricted/encrypted backups. Restoration is conditional on actual reversibility, never a promised rollback for schema/database changes. Before implementing: obtain DEP-001/002/003 evidence, add reviewed version capability profiles, then prove idempotency/reboot/identity retention on a disposable Ubuntu VM. Add host locks and fresh state reconciliation when real mutations arrive. Do not expand Phase 1 to make its tests simulate a successful installation.

For a new secret provider, define a narrow reference schema and secure transport, register values before any output, test exception/payload leakage, clean up temporary material and preserve the same opaque interface. Azure Key Vault and dispatch require Phase 3 and DEP-004; no credentials belong in tests or Git.

## Validation and coding conventions

Run `./scripts/test.sh` then `./scripts/lint.sh`. Tests cover real framework parsing, decision logic, output and negative paths with synthetic fixtures. Ubuntu fixture runs are simulated host observations, not simulated product success. Local subprocess checks exercise the actual launchers. Shell syntax is always checked; shellcheck/shfmt skips are printed if tools are missing. Tests inject time, run IDs, platform and package-tool lookup without production spoof-host flags.

Keep functions small; retain type-oriented provider contracts and explicit FrameworkError names. Do not use eval, shell-sourced configuration, unquoted shell arguments, print/raw logging in production code, network probes in dry-run or broad exception details in results. Ruff and schemas provide repeatable checks; human review remains necessary before adding privileged operations.
