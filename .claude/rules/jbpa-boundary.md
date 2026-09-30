# External JBPA caller boundary

Applies when changing or operating external orchestration/handoff code.

- Start only after the VM exists. JBPA DOES NOT CREATE VIRTUAL MACHINES.
- The external caller may provision the VM, attach identity, configure network, deliver a verified, pinned JBPA release and configuration, invoke JBPA and retrieve its result.
- JBPA alone owns Private Agent package operations, registration input, Harmony authentication, Agent Services, synchronization, health, drain, uninstall and reinstall.
- Consume exit code plus schema-valid result JSON. Never infer success from Jitterbit service names, vendor logs, Harmony markers or TranDb in caller code.
- Never read `credentials.txt`, print `register.json`, expose secret-provider values, run `dpkg` for PA lifecycle, or compose REINSTALL from separate commands.
- Never bypass an artifact hash or the qualification policy except an explicitly authorized controlled test. Preflight must confirm the actual host and state before mutation.
