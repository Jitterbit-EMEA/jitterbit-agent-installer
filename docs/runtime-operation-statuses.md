# Native PA operation status model

The PA 12.10.1.1 Ubuntu 24.04 TranDb `operationlogtab` provider queries status codes through the bundled PostgreSQL client. This status mapping and active-set query were supplied with live test evidence; the repository provider independently returned a successful count of zero from the same QA VM on 2026-09-25.

| Code | Name | Drain classification |
| --- | --- | --- |
| 0 | Submitted | Active |
| 1 | Pending | Active |
| 2 | Cancelled | Terminal |
| 3 | Running | Active |
| 4 | Success | Terminal |
| 5 | Success_With_Info | Terminal |
| 6 | Success_With_Warning | Terminal |
| 7 | Error | Terminal |
| 8 | Cancel_Requested | Active |
| 9 | Success_With_Child_Error | Terminal |
| 10 | Received | Active |
| 11 | SOAP_Fault | Terminal |

Drain completion requires `SELECT COUNT(*) FROM operationlogtab WHERE status IN (0,1,3,8,10)` to return zero. Query failure is never interpreted as zero. The provider resolves `PG_HOME` from `/etc/sysconfig/jitterbit` without sourcing it, reads only `User`, `Password`, and `Port` from `[DbInfo]` in `jitterbit.conf`, and runs bundled `psql` with `LD_LIBRARY_PATH=$PG_HOME/lib` and the password in the subprocess environment. The password is excluded from command arguments, output, and structured results.

See [provider evidence](../evidence/pa-12.10.1.1/ubuntu-24.04/uninstall/pending-operation-provider.yaml) and [uninstall runbook](runbooks/native-linux-pa-uninstall.md).
