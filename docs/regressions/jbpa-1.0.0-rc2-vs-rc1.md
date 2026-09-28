# JBPA 1.0.0-rc2 vs rc1

| Dimension | Change |
| --- | --- |
| Install lifecycle | UNCHANGED; facade forwarding/audit metadata only |
| Registration | UNCHANGED |
| Health | UNCHANGED |
| Uninstall | UNCHANGED |
| Enterprise | UNCHANGED |
| Catalogue and platform support | UNCHANGED; no promotion |
| Bootstrap | CHANGED: optional seventh false/true argument, default false; true requires controlled-test |
| Azure caller contract | CHANGED: strict boolean allowUnqualified, safe argv mapping |
| Qualification guard | Exact resolved package must match qualified catalogue package, in addition to exact OS/version/architecture |
| Result | Additive details.qualification audit metadata; schema 1.0 unchanged |
| Packaging | Bootstrap/settings and release/bootstrap notes included in rc2 |

The regression entry point already forwards the same override to install; its lifecycle implementation is unchanged. Explicit override permits only an experimental policy path and does not alter catalogue state. Controlled tests stop at the next preflight/invocation boundary; they do not claim successful installations. Actual Ubuntu 22.04 and Azure qualification are pending.
