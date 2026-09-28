# JBPA 1.0.0-rc3 versus rc2

| Area | Change and evidence |
| --- | --- |
| INSTALL | Existing native installation reused; additive shared host-readiness gate before mutation. Unsupported/unconfirmed readiness now blocks dispatch; this is an intentional expanded prerequisite, not unchanged preflight behavior |
| Registration | Existing native register.json/credentials/restart and mandatory initial registration markers unchanged |
| Health | Existing mandatory Harmony/Agent Services/synchronization/core health implementation unchanged |
| UNINSTALL | Existing drain/provider/removal/verification unchanged; an injected lock context permits safe composition under the shared REINSTALL outer lock |
| Enterprise | Existing runtime implementation unchanged |
| REINSTALL | New first-class on-host operation; target validation before destruction, complete removal, independent clean-host check, pinned fresh install and composed result |
| Host preflight | Expanded shared readiness engine for validate/install/reinstall |
| External caller | RC3 REINSTALL accepted directly; RC2 remains explicitly unsupported for that operation |
| Result schema | 1.0 retained; optional structured details sections and optional manifest capabilities added |
| Infrastructure provisioning | OUTSIDE JBPA SCOPE |

All former tests retain their assertions. Tests that already mock bootstrap execution also explicitly mock the added readiness boundary; new tests exercise that boundary's failure and success cases. Historical RC2 caller fixtures explicitly retain version rc2 while current runtime version is rc3. Archive verification now checks manifest/prefix/embedded runtime version agreement for explicitly supported rc2 or current rc3; independently expected digest remains required for deployment provenance.

RC2 archive, sidecar and staged manifest digests are compared with the pre-change snapshot. No RC2 file is rebuilt or modified. New behavior is MOCK/LOCAL TESTED, not live-qualified. GATE-10/GATE-13 remain pending.
