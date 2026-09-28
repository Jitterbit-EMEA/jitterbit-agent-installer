# Phase 2 implementation brief

Source attachment SHA-256: `911c636828f1e49c5d43d9fad24ad0aab7d7b7f4f686695874d01fca529f0a82`.

The brief authorized implementation of the native Linux workflow with these boundaries:

- Live tuple: PA 12.9.2.2, Ubuntu 24.04.5 LTS, amd64, native Debian package, Agent Registration token, no proxy, Harmony EMEA West.
- Requested regression tuple: PA 12.10, Ubuntu 22.04, amd64. This must not inherit live qualification.
- Validate package name, architecture, exact version and configured digest before installation.
- Install with `silent_install=1`; absent credentials during initial service startup are expected.
- Preserve existing credentials. Both credentials and register.json present initially is `REGISTRATION_STATE_CONFLICT`.
- Create `/opt/jitterbit/Resources/register.json` without exposing the token; use `retryCount`.
- Restart once and poll for 300 seconds by default. A delayed agent log is a waiting state.
- Require registration completion, credentials, Harmony auth, Agent Services, synchronization and healthy local services.
- Do not treat generic WARN or ERROR entries as failure.
- Use bounded package locks, never delete lock files, and do not run a general OS upgrade.

This normalized copy preserves every boundary used by the adapter while omitting repetition and secrets.
