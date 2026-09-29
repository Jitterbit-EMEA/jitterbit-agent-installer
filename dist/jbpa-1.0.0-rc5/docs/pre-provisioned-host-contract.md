# Pre-provisioned host contract

JBPA starts after the host exists. The external orchestrator prepares supported Linux, architecture, root/sudo access, CPU/memory/disk, package repositories, DNS/time/egress and existing identity/RBAC. No Azure infrastructure configuration is required by JBPA. Host creation and preparation remain outside product scope.

RC3 implements the [canonical structured host-readiness engine](preflight-contract.md) shared by validate, INSTALL and REINSTALL. It checks actual OS/version/codename/kernel/architecture, privilege, package audit/locks, existing-metadata dependency resolution, resource policy, operational free space, configured DNS/TLS, synchronization, secret-provider authentication/references and existing product state. Unknown blocking observations deny execution. The result documents each check's timestamp, provider, interpreted state, reason and non-secret evidence.

Root execution is required for mutation; JBPA reports sudo availability but never escalates itself. Dry-run skips network and secret retrieval and cannot authorize execution. Agent Services authentication remains a mandatory product check after registration, explicitly unconfirmed before installation. Repository simulation proves existing metadata resolution without refreshing or upgrading packages; actual preparation retains its normal failure gates.

Supported REINSTALL starts are CLEAN_HOST, AGENT_INSTALLED_REGISTERED and AGENT_INSTALLED_UNREGISTERED. Partial/unknown state is rejected. Complete removal must independently produce a clean snapshot before a fresh install. Credentials contents are never read for discovery.

For Ubuntu 22.04 use amd64/x86_64 and the existing documented technical minimum: four CPUs, eight GiB memory and 50 GiB disk. The historical Ubuntu 24.04 two-CPU controlled QA exception remains confined to that target. Operational free-space margins are separately documented and are not production vendor sizing approval.

Required egress includes approved artifact storage, configured Harmony HTTPS/Agent Services, the approved Python index for framework bootstrap and OS repositories for dependency preparation. Azure secret providers additionally need IMDS/Key Vault, with identity and access granted externally. Network, DNS, clock and identity creation are never JBPA actions.

RC2 remains historical immutable evidence with its older readiness limitations. RC3 runtime behavior is MOCK/LOCAL TESTED; actual Ubuntu 22.04 installation, registration, synchronization and health observations are still required before live qualification.
