#!/usr/bin/env python3
"""Read-only live TranDb discovery; credentials remain local to the PA host."""

import argparse
import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path[:0] = ["/opt/jbpa/releases/jbpa-1.0.0-rc9/lib", "/opt/jbpa/releases/jbpa-1.0.0-rc9/src"]
from jbpa.pending_operations import TranDbOperationProvider  # noqa: E402

QUERIES = []


def readonly_runner(argv, **kw):
    env = dict(kw.get("env", {}))
    env.pop("PGOPTIONS", None)
    kw["env"] = env
    return subprocess.run([argv[0], "-q", *argv[1:]], **kw)


provider = TranDbOperationProvider(runner=readonly_runner)


def ident(name):
    return '"' + name.replace('"', '""') + '"'


def query(label, sql):
    start = time.monotonic()
    wrapped = (
        "BEGIN READ ONLY; SET LOCAL statement_timeout='5s'; SET LOCAL lock_timeout='1s'; SELECT COALESCE(jsonb_agg(to_jsonb(q)), '[]'::jsonb)::text FROM ("
        + sql.strip().rstrip(";")
        + ") q; ROLLBACK;"
    )
    try:
        data = json.loads(provider._query(wrapped))
        status = "SUCCESS"
    except Exception as exc:
        data = None
        status = "UNAVAILABLE"
        reason = type(exc).__name__
    QUERIES.append(
        {
            "label": label,
            "status": status,
            "elapsedMs": round((time.monotonic() - start) * 1000),
            "sql": sql,
            "reason": None if status == "SUCCESS" else reason,
        }
    )
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    out = {
        "observedAtUtc": datetime.now(timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "access": "Local psql using DbInfo credentials; values not returned",
        "readOnlyEnforced": True,
        "readOnlyMethod": "Each query uses explicit BEGIN READ ONLY and ends ROLLBACK; no startup PGOPTIONS (PgBouncer compatibility)",
        "statementTimeoutMs": 5000,
    }
    out["database"] = query(
        "database_identity",
        "SELECT current_database() database, current_setting('server_version') server_version,current_setting('TimeZone') database_timezone,current_setting('transaction_read_only') transaction_read_only,pg_database_size(current_database()) database_bytes,pg_is_in_recovery() in_recovery",
    )
    if not out["database"] or out["database"][0]["transaction_read_only"] != "on":
        raise SystemExit("READ_ONLY_CONNECTION_NOT_VERIFIED")
    out["tables"] = (
        query(
            "table_inventory",
            "SELECT n.nspname schema,c.relname name,c.relkind kind,c.reltuples estimated_rows,pg_relation_size(c.oid) heap_bytes,pg_indexes_size(c.oid) index_bytes,pg_total_relation_size(c.oid) total_bytes,c.relrowsecurity row_security,has_table_privilege(c.oid,'SELECT') can_select FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind IN ('r','p','m') AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' ORDER BY n.nspname,c.relname",
        )
        or []
    )
    out["columns"] = (
        query(
            "column_inventory",
            "SELECT table_schema schema,table_name name,column_name AS \"column\",ordinal_position position,data_type,udt_name,is_nullable,character_maximum_length,max_numeric_precision.numeric_precision,column_default IS NOT NULL has_default,is_identity,is_generated FROM information_schema.columns max_numeric_precision WHERE table_schema NOT IN ('pg_catalog','information_schema') AND table_schema NOT LIKE 'pg_toast%' ORDER BY table_schema,table_name,ordinal_position",
        )
        or []
    )
    out["constraints"] = (
        query(
            "keys_relationships",
            "SELECT n.nspname schema,c.relname name,k.conname constraint_name,k.contype kind,pg_get_constraintdef(k.oid) definition FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND k.contype IN ('p','f','u') ORDER BY n.nspname,c.relname,k.conname",
        )
        or []
    )
    out["indexes"] = (
        query(
            "index_inventory",
            "SELECT schemaname schema,tablename name,indexname,indexdef FROM pg_indexes WHERE schemaname NOT IN ('pg_catalog','information_schema') AND schemaname NOT LIKE 'pg_toast%' ORDER BY schemaname,tablename,indexname",
        )
        or []
    )
    out["views"] = (
        query(
            "view_inventory",
            "SELECT table_schema schema,table_name name FROM information_schema.views WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY table_schema,table_name",
        )
        or []
    )
    out["functions"] = (
        query(
            "function_inventory",
            "SELECT n.nspname schema,p.proname name,pg_get_function_identity_arguments(p.oid) arguments,pg_get_function_result(p.oid) result_type,p.provolatile volatility,p.prosecdef security_definer FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') ORDER BY n.nspname,p.proname",
        )
        or []
    )
    out["extensions"] = (
        query(
            "extension_inventory",
            "SELECT extname name,extversion version FROM pg_extension ORDER BY extname",
        )
        or []
    )
    out["databaseStats"] = query(
        "database_counters",
        "SELECT datname, numbackends,xact_commit,xact_rollback,blks_read,blks_hit,tup_returned,tup_fetched,tup_inserted,tup_updated,tup_deleted,conflicts,temp_files,temp_bytes,deadlocks,stats_reset FROM pg_stat_database WHERE datname=current_database()",
    )
    out["activity"] = query(
        "connection_state_counts",
        "SELECT state,wait_event_type,wait_event,count(*) sessions FROM pg_stat_activity WHERE datname=current_database() GROUP BY state,wait_event_type,wait_event ORDER BY count(*) DESC",
    )
    out["lockSummary"] = query(
        "lock_summary",
        "SELECT locktype,mode,granted,count(*) locks FROM pg_locks GROUP BY locktype,mode,granted ORDER BY locktype,mode,granted",
    )
    out["tableStats"] = query(
        "table_counters",
        "SELECT schemaname schema,relname name,seq_scan,idx_scan,n_live_tup,n_dead_tup,n_tup_ins,n_tup_upd,n_tup_del,last_vacuum,last_autovacuum,last_analyze,last_autoanalyze FROM pg_stat_user_tables ORDER BY schemaname,relname",
    )
    out["settings"] = query(
        "nonsecret_settings",
        "SELECT name,setting,unit FROM pg_settings WHERE name IN ('max_connections','shared_buffers','effective_cache_size','work_mem','maintenance_work_mem','autovacuum','track_counts','track_io_timing','server_encoding','timezone','DateStyle') ORDER BY name",
    )
    cols = {}
    for col in out["columns"]:
        cols.setdefault((col["schema"], col["name"]), []).append(col)
    if args.profile:
        for table in out["tables"]:
            qualified = ident(table["schema"]) + "." + ident(table["name"])
            key = (table["schema"], table["name"])
            if not table["can_select"]:
                table["countStatus"] = "NO_SELECT_PRIVILEGE"
                continue
            count = query("count:" + ".".join(key), "SELECT count(*) rows FROM " + qualified)
            table["exactRows"] = count[0]["rows"] if count else None
            table["countStatus"] = "SUCCESS" if count else "UNAVAILABLE"
            if not table["exactRows"]:
                continue
            timestamps = [
                c for c in cols.get(key, []) if c["data_type"].startswith(("timestamp", "date"))
            ]
            if timestamps:
                expr = []
                for c in timestamps:
                    q = ident(c["column"])
                    a = c["column"]
                    expr.extend(
                        [
                            "min(" + q + ")::text AS " + ident(a + "_min"),
                            "max(" + q + ")::text AS " + ident(a + "_max"),
                            "count(*) FILTER (WHERE " + q + " IS NULL) AS " + ident(a + "_nulls"),
                        ]
                    )
                table["timeCoverage"] = query(
                    "time_coverage:" + ".".join(key),
                    "SELECT " + ",".join(expr) + " FROM " + qualified,
                )
            states = [
                c
                for c in cols.get(key, [])
                if c["column"].lower()
                in ("status", "state", "enabled", "is_enabled", "operation_status")
                and c["data_type"]
                in ("integer", "smallint", "bigint", "boolean", "character varying", "text")
            ]
            if states:
                table["statusDistributions"] = {}
                for c in states:
                    table["statusDistributions"][c["column"]] = query(
                        "status_distribution:" + ".".join(key) + ":" + c["column"],
                        "SELECT "
                        + ident(c["column"])
                        + " value,count(*) rows FROM "
                        + qualified
                        + " GROUP BY "
                        + ident(c["column"])
                        + " ORDER BY count(*) DESC LIMIT 30",
                    )
        safe_names = {
            "operation_instance_guid",
            "operation_guid",
            "operation_id",
            "project_name",
            "operation_name",
            "environment_id",
            "agent_id",
            "status",
            "entered_ts",
            "started_ts",
            "status_ts",
            "finished_ts",
            "ended_ts",
        }
        out["operationSamples"] = []
        for table in out["tables"]:
            if table["name"].lower() != "operationlogtab":
                continue
            fields = [
                c["column"]
                for c in cols.get((table["schema"], table["name"]), [])
                if c["column"].lower() in safe_names
            ]
            if fields:
                out["operationSamples"] = query(
                    "safe_operation_run_sample",
                    "SELECT "
                    + ",".join(ident(f) for f in fields)
                    + " FROM "
                    + ident(table["schema"])
                    + "."
                    + ident(table["name"])
                    + " LIMIT 20",
                )
    out["queries"] = QUERIES
    out["summary"] = {
        "tables": len(out["tables"]),
        "columns": len(out["columns"]),
        "constraints": len(out["constraints"]),
        "indexes": len(out["indexes"]),
        "views": len(out["views"]),
        "functions": len(out["functions"]),
        "queries": len(QUERIES),
        "unavailableQueries": sum(q["status"] != "SUCCESS" for q in QUERIES),
    }
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
