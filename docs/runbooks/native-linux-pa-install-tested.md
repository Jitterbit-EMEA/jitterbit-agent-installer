# Native Linux Private Agent install runbook

Evidence-qualified tuple: PA 12.9.2.2 on Ubuntu 24.04 amd64, native `.deb`, no proxy, Agent Registration token, Harmony EMEA West. PA 12.10 on Ubuntu 22.04 requires regression validation.

The implementation in `src/jbpa/native_linux.py` executes this order:

1. Validate no-proxy native registration inputs and inspect existing credentials and registration state.
2. Use apt's bounded `DPkg::Lock::Timeout`; refresh indexes and install `odbcinst`, `unixodbc` and `unzip`.
3. Create private staging, download the catalogue artifact, verify SHA-256, and inspect Package, Architecture and Version with `dpkg-deb --field`.
4. Run `env silent_install=1 dpkg --install` and confirm core product paths.
5. If credentials do not exist, resolve the token in memory and atomically create mode-0600 `register.json` owned by `jitterbit:jitterbit`.
6. Restart exactly once. Poll without failing while the main log is absent.
7. Require all cloud/runtime success gates and all four local services plus `All services are running`.
8. Clear the in-memory secret in every outcome and return a secret-free result.

The adapter never deletes package locks, credentials or a pre-existing registration file. Existing credentials suppress a new registration document. Both registration files present initially is a conflict. Proxy and optional SSH/SSL/Java trust paths fail closed because the supplied live evidence does not qualify them.

On success, the adapter confirms credentials, Harmony authentication, Agent Services, synchronization and local health before removing a remaining `register.json`. During registration pending or failure it preserves the file and records the failure state. Polling reads only log content added after the single restart, avoiding stale success markers from a previous run. An already registered agent does not require automatic-registration markers on restart.

The PA 12.10.1.1 URL and locally calculated digest are catalogued for an explicit `--controlled-test` run on Ubuntu 24.04 only. Production execution remains blocked until independent integrity evidence and production approval are recorded. The supplied vendor URL and its checksum header are insufficient independent integrity evidence. The controlled run also requires a clean registration target; see the [Phase 2C preflight](../../evidence/pa-12.10.1.1/ubuntu-24.04/preflight.yaml).
