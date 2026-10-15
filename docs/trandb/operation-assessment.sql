-- QA psql query: pass -v root_run_guid=<validated UUID>.
-- Production provider must use driver-bound values, source authorization and caps.
-- No raw message, properties, scripts, credentials or payload returned.
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
WITH scoped AS (
    SELECT operation_log_id,operation_instance_guid,parent_operation_instance_guid,
           root_operation_instance_guid,operation_id,operation_name,status,
           entered_ts,started_ts,status_ts,agent_id,environment_id
    FROM operationlogtab
    WHERE operation_instance_guid=:'root_run_guid'
       OR root_operation_instance_guid=:'root_run_guid'
), messages AS (
    SELECT m.operation_instance_guid,count(*) message_count
    FROM operationmessagetab m
    WHERE EXISTS (SELECT 1 FROM scoped s
                  WHERE s.operation_instance_guid=m.operation_instance_guid)
    GROUP BY m.operation_instance_guid
)
SELECT s.operation_id,s.operation_name,s.agent_id,s.environment_id,s.status,
       count(*) execution_rows,
       count(DISTINCT s.operation_instance_guid) distinct_executions,
       count(*) FILTER (WHERE s.operation_instance_guid IS NULL) missing_run_identity,
       min(s.entered_ts) first_submitted_at,max(s.entered_ts) last_submitted_at,
       min(s.started_ts) first_started_at,max(s.status_ts) last_status_changed_at,
       count(*) FILTER (
           WHERE s.parent_operation_instance_guid IS NOT NULL
             AND s.parent_operation_instance_guid<>''
             AND NOT EXISTS (SELECT 1 FROM scoped p
                             WHERE p.operation_instance_guid=s.parent_operation_instance_guid)
       ) parents_absent_in_root_scope,
       sum(coalesce(m.message_count,0)) diagnostic_message_count
FROM scoped s LEFT JOIN messages m USING(operation_instance_guid)
GROUP BY s.operation_id,s.operation_name,s.agent_id,s.environment_id,s.status
ORDER BY s.operation_id,s.status;
ROLLBACK;
