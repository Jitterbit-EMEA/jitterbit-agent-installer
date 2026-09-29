"""Read-only TranDb active-operation provider for the qualified native agent."""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ACTIVE_STATUSES = (0, 1, 3, 8, 10)
STATUS_NAMES = {
    0: "Submitted",
    1: "Pending",
    2: "Cancelled",
    3: "Running",
    4: "Success",
    5: "Success_With_Info",
    6: "Success_With_Warning",
    7: "Error",
    8: "Cancel_Requested",
    9: "Success_With_Child_Error",
    10: "Received",
    11: "SOAP_Fault",
}
COUNT_SQL = "SELECT COUNT(*) FROM operationlogtab WHERE status IN (0,1,3,8,10);"
SUMMARY_SQL = (
    "SELECT status, COUNT(*) FROM operationlogtab "
    "WHERE status IN (0,1,3,8,10) GROUP BY status ORDER BY status;"
)
DETAIL_SQL = """SELECT operation_instance_guid, project_name, operation_name,
CASE status
WHEN 0 THEN 'Submitted' WHEN 1 THEN 'Pending' WHEN 2 THEN 'Cancelled'
WHEN 3 THEN 'Running' WHEN 4 THEN 'Success' WHEN 5 THEN 'Success_With_Info'
WHEN 6 THEN 'Success_With_Warning' WHEN 7 THEN 'Error'
WHEN 8 THEN 'Cancel_Requested' WHEN 9 THEN 'Success_With_Child_Error'
WHEN 10 THEN 'Received' WHEN 11 THEN 'SOAP_Fault'
ELSE 'Unknown(' || status || ')' END AS status,
entered_ts, started_ts, status_ts
FROM operationlogtab WHERE status IN (0,1,3,8,10)
ORDER BY COALESCE(started_ts, entered_ts);"""


class OperationQueryError(Exception):
    """No raw database or configuration error is exposed to callers."""


def _assignment(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _pg_home(env_text):
    for line in env_text.splitlines():
        match = re.fullmatch(r"\s*(?:export\s+)?PG_HOME\s*=\s*(.*?)\s*", line)
        if match:
            path = _assignment(match[1])
            if path.startswith("/") and "$" not in path and "`" not in path:
                return Path(path)
    raise OperationQueryError()


def _db_info(conf_text):
    section = None
    fields = {}
    for line in conf_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("#", ";")) or not stripped:
            continue
        match = re.fullmatch(r"\[([^]]+)\]", stripped)
        if match:
            section = match[1]
            continue
        if section != "DbInfo":
            continue
        match = re.match(r"\s*(User|Password|Port)\s*=\s*(.*)$", line)
        if match and match[1] not in fields:
            fields[match[1]] = _assignment(match[2])
    if not fields.get("User") or not fields.get("Password"):
        raise OperationQueryError()
    port = fields.get("Port", "6432")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise OperationQueryError()
    return fields["User"], fields["Password"], port


class TranDbOperationProvider:
    """Use bundled psql and an in-memory password; never invoke a shell."""

    def __init__(
        self,
        *,
        environment_file="/etc/sysconfig/jitterbit",
        config_file="/opt/jitterbit/jitterbit.conf",
        runner=subprocess.run,
    ):
        self.environment_file = Path(environment_file)
        self.config_file = Path(config_file)
        self.runner = runner

    def _runtime(self):
        try:
            home = _pg_home(self.environment_file.read_text())
            user, password, port = _db_info(self.config_file.read_text())
            psql = home / "bin/psql"
            library = home / "lib"
            if not psql.is_file() or not (library / "libpq.so.5").exists():
                raise OperationQueryError()
            return psql, library, user, password, port
        except (OSError, UnicodeError) as exc:
            raise OperationQueryError() from exc

    def _query(self, sql):
        psql, library, user, password, port = self._runtime()
        env = {**os.environ, "PGPASSWORD": password, "LD_LIBRARY_PATH": str(library)}
        argv = [
            str(psql),
            "-X",
            "-A",
            "-t",
            "-F",
            "\t",
            "-v",
            "ON_ERROR_STOP=1",
            "-h",
            "127.0.0.1",
            "-p",
            port,
            "-U",
            user,
            "-d",
            "TranDb",
            "-c",
            sql,
        ]
        try:
            result = self.runner(argv, env=env, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OperationQueryError() from exc
        if result.returncode:
            raise OperationQueryError()
        return result.stdout.strip()

    def active_count(self):
        value = self._query(COUNT_SQL)
        if not re.fullmatch(r"\d+", value):
            raise OperationQueryError()
        return int(value)

    def summary(self):
        rows = []
        for line in self._query(SUMMARY_SQL).splitlines():
            try:
                status, count = line.split("\t")
                number = int(status)
                if number not in ACTIVE_STATUSES or not count.isdigit():
                    raise ValueError()
                rows.append((STATUS_NAMES[number], int(count)))
            except ValueError as exc:
                raise OperationQueryError() from exc
        return rows

    def details(self):
        return self._query(DETAIL_SQL)

    def debug_info(self):
        psql, library, user, _, port = self._runtime()
        return {"psql": str(psql), "library": str(library), "user": user, "port": port}


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise OperationQueryError()


def main(argv=None, *, provider=None, stdout=None, stderr=None):
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = SafeParser(description="Query active Jitterbit operations")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--count", action="store_true")
    modes.add_argument("--quiet", action="store_true")
    modes.add_argument("--summary", action="store_true")
    parser.add_argument("--debug", action="store_true")
    try:
        args = parser.parse_args(argv)
        if args.debug and (args.count or args.quiet):
            raise OperationQueryError()
        provider = provider or TranDbOperationProvider()
        count = provider.active_count()
        if args.count:
            stdout.write(f"{count}\n")
        elif not args.quiet:
            stdout.write("Jitterbit Active Operations\n===========================\n")
            if args.summary:
                for name, amount in provider.summary():
                    stdout.write(f"{name}: {amount}\n")
            elif args.debug and count:
                stdout.write(provider.details() + "\n")
            elif count:
                stdout.write("Operation identifiers and names withheld; use --debug for details.\n")
            stdout.write(f"Active operation count: {count}\n")
            if args.debug:
                for key, value in provider.debug_info().items():
                    stdout.write(f"{key}: {value}\n")
        return 2 if count else 0
    except OperationQueryError:
        stderr.write("PENDING_OPERATION_QUERY_FAILED\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
