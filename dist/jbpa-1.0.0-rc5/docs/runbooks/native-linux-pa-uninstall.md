# Native Linux PA 12.10.1.1 complete uninstall

Target: Ubuntu 24.04.5 amd64, native `.deb`, local bundled TranDb. Run as root on a disposable or explicitly decommissioned host. The framework files and `/var/lib/jbpa` remain in place.

1. Inspect package status, Jitterbit-owned processes, product path, registration-file presence, account, command links and startup integration. Capture metadata only.
2. Run `bin/jbpa-pending-operations --count`. Exit `0` means count zero; exit `2` means active operations; exit `1` means query failure. A nonzero active count is expected and does not block drain-pause.
3. Run `bin/jbpa uninstall --complete --dry-run` for a read-only plan. Then invoke `bin/jbpa uninstall --complete --result-file /var/lib/jbpa/results/UNIQUE.json` with a new result filename.
4. The command runs `/opt/jitterbit/bin/jitterbit-utils --drain-pause`, polls TranDb every five seconds for up to 1,800 seconds, and proceeds only when status `IN (0,1,3,8,10)` has count zero. Query failure or timeout stops the default workflow without removing the package.
5. It runs `jitterbit-utils --drain-stop`, polls Jitterbit-owned process executables for up to 300 seconds, and refuses package removal if they remain. Only an explicit `--force` permits `jitterbit stop` after a recorded timeout. [Jitterbit's Linux agent guidance](https://docs.jitterbit.com/agent/linux/) describes drain-pause, drain-stop and hard-stop semantics.
6. After stop confirmation, it runs `apt-get -o DPkg::Lock::Timeout=120 remove --autoremove -y jitterbit-agent`, purges residual package config, removes the `jitterbit` user, inventories leftovers, and removes `/opt/jitterbit`. It removes only command symlinks verified to target `/opt/jitterbit` and the exact package startup files. It never manually removes shared OS packages merely because Jitterbit used them.
7. The final check requires package, user, product root, credentials, registration input, bundled PostgreSQL, product processes, Jitterbit command links, and startup integration all absent. A repeated run returns `ALREADY_UNINSTALLED` successfully.

Useful flags: `--drain-pause-timeout-seconds 1800`, `--operation-poll-interval-seconds 5`, `--stop-timeout-seconds 300`, and `--stop-poll-interval-seconds 5`. `--remove-harmony-agent` does not delete a cloud record; it marks manual/supported cleanup required. Never capture `jitterbit.conf` password, `credentials.txt`, or `register.json` contents.
