# Onboard a PA release

1. Add exact logical release, four-component package version, amd64 filename and authoritative URL to config/versions.yaml. Start artifact status KNOWN and runtime AVAILABLE_UNQUALIFIED; do not invent a contract.
2. Run jbpa artifact intake --version VERSION. Inspect dpkg-deb fields, exact version/architecture/dependencies, byte size, local SHA-256 and immutable metadata manifest. Independently review provenance before approval.
3. Explicitly authorize a clean disposable VM and non-production Harmony/Key Vault configuration. Run regression with --live --allow-unqualified; BASIC leaves the agent installed, FULL_LIFECYCLE additionally drains/uninstalls/reinstalls.
4. Review the captured initial runtime contract and all unobserved dimensions. CONTRACT_CHANGED requires a version-specific adapter or explicit compatibility review. Dependency/path/registration/service changes are not silently accepted. Timing-only differences may be classified CONTRACT_COMPATIBLE_MINOR_CHANGES by evidence review; no automated promotion occurs.
5. After successful scoped live qualification, add a schema-valid runtime contract and evidence, update the exact platform/scope, approve the QA digest and review aliases separately. Production approval is separate.
6. Run scripts/validate.sh, build and verify a new framework release candidate.

Compatible contracts use the existing native adapter with catalogue/contract data changes. The Phase 2G runner compares observed initial-runtime dimensions; restart/truststore/drain behavior needs explicit branch evidence, not a blanket compatible claim.
