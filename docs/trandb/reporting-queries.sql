-- Read-only TranDb query catalogue. Catalogue defined in scripts/management/trandb_reporting.py; executed by validate-trandb-reporting.py.
-- LIMIT 100 below is a SQL example; executable reporting defaults to 500 (maximum 2000).
-- Every query uses a separate transaction. No credentials or message contents included.

-- operation_definitions
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT o.operation_id,o.guid operation_guid,o.operation_name,o.operation_type_id,o.environment_id,o.timeoutseconds,o.ignore_history,o.targeted_state,o.actual_state,o.target_agent_id,o.success_operation_id,o.failure_operation_id,o.soap_fault_operation_id,p.project_id,p.projectname,e.environmentname,e.agentgroup_id FROM operationstab o LEFT JOIN projectoperationstab po ON po.item_id=o.operation_id LEFT JOIN projectstab p ON p.project_id=po.project_id LEFT JOIN environmentstab e ON e.id=o.environment_id ORDER BY o.operation_id LIMIT 100;
ROLLBACK;

-- operation_runs
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT operation_log_id,operation_instance_guid,root_operation_instance_guid,parent_operation_instance_guid,operation_id,operation_guid,operation_name,project_guid,project_name,environment_id,environment_name,agent_id,agent_name,organization_id,status,entered_ts,started_ts,status_ts,extract(epoch FROM (started_ts-entered_ts))*1000 queue_delay_ms,extract(epoch FROM (status_ts-started_ts))*1000 status_transition_elapsed_ms FROM operationlogtab ORDER BY entered_ts DESC,operation_log_id DESC LIMIT 100;
ROLLBACK;

-- run_status_counts
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT status,count(*) runs FROM operationlogtab GROUP BY status ORDER BY status;
ROLLBACK;

-- run_grain_checks
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT count(*) rows,count(DISTINCT operation_log_id) distinct_log_ids,count(DISTINCT operation_instance_guid) distinct_run_guids,count(*) FILTER (WHERE operation_instance_guid IS NULL OR operation_instance_guid='') missing_run_guid,count(*) FILTER (WHERE started_ts<entered_ts) start_before_entry,count(*) FILTER (WHERE status_ts<started_ts) status_before_start,count(*) FILTER (WHERE entered_ts IS NULL) missing_entered,count(*) FILTER (WHERE started_ts IS NULL) missing_started,count(*) FILTER (WHERE status_ts IS NULL) missing_status_time FROM operationlogtab;
ROLLBACK;

-- logical_relationship_checks
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT (SELECT count(*) FROM operationlogtab l LEFT JOIN operationstab o ON o.operation_id=l.operation_id WHERE o.operation_id IS NULL) log_missing_definition,(SELECT count(*) FROM operationlogtab l LEFT JOIN operationinstancetab i ON i.operation_instance_guid=l.operation_instance_guid WHERE i.operation_instance_id IS NULL) log_missing_instance,(SELECT count(*) FROM operationlogtab l WHERE l.parent_operation_instance_guid IS NOT NULL AND l.parent_operation_instance_guid<>'' AND NOT EXISTS (SELECT 1 FROM operationlogtab p WHERE p.operation_instance_guid=l.parent_operation_instance_guid)) missing_parent_run,(SELECT count(*) FROM operationmessagetab m WHERE NOT EXISTS (SELECT 1 FROM operationlogtab l WHERE l.operation_instance_guid=m.operation_instance_guid)) messages_missing_run,(SELECT count(*) FROM projectoperationstab po WHERE NOT EXISTS (SELECT 1 FROM projectstab p WHERE p.project_id=po.project_id)) project_map_missing_project;
ROLLBACK;

-- child_runs
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT p.operation_instance_guid parent_run,p.operation_name parent_name,c.operation_instance_guid child_run,c.operation_name child_name,c.status child_status FROM operationlogtab c JOIN operationlogtab p ON p.operation_instance_guid=c.parent_operation_instance_guid ORDER BY c.entered_ts DESC,c.operation_log_id DESC LIMIT 100;
ROLLBACK;

-- operation_message_metadata
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT operation_message_id,operation_instance_guid,entered_ts,field_name,char_length(message) message_characters FROM operationmessagetab ORDER BY entered_ts DESC,operation_message_id DESC LIMIT 100;
ROLLBACK;

-- log_message_metadata
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT operation_log_id,operation_name,char_length(message) message_characters,debug_mode_enabled,debug_file_present,projectexplicitagentversion FROM operationlogtab ORDER BY operation_log_id DESC LIMIT 100;
ROLLBACK;

-- operation_property_keys
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT keyname,count(*) entries,min(char_length(keyvalue)) min_value_length,max(char_length(keyvalue)) max_value_length FROM operationpropertiestab GROUP BY keyname ORDER BY keyname;
ROLLBACK;

-- log_sync_backlog
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT table_id,is_synced,priority,count(*) items FROM logsynctab GROUP BY table_id,is_synced,priority ORDER BY table_id,is_synced,priority;
ROLLBACK;

-- deployment_summary
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT environment_id,agentgroup_id,entitytypeid,isdeleted,syncflag,errorcount,count(*) records,min(deploytimestamp) first_raw_timestamp,max(deploytimestamp) last_raw_timestamp FROM deploylogtab GROUP BY environment_id,agentgroup_id,entitytypeid,isdeleted,syncflag,errorcount ORDER BY entitytypeid;
ROLLBACK;

-- key_names_only
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT key_name,key_type,count(*) entries FROM key_values GROUP BY key_name,key_type ORDER BY key_name;
ROLLBACK;

-- view_column_inventory
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT table_name view_name,column_name field,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name IN (SELECT table_name FROM information_schema.views WHERE table_schema='public') ORDER BY table_name,ordinal_position;
ROLLBACK;

-- read_only_capability
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT current_setting('transaction_read_only') transaction_read_only,has_database_privilege(current_database(),'CONNECT') can_connect,has_schema_privilege('public','USAGE') can_use_schema;
ROLLBACK;

-- catalog_join_cardinality
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT count(*) joined_rows,count(DISTINCT o.operation_id) distinct_operations FROM operationstab o LEFT JOIN projectoperationstab po ON po.item_id=o.operation_id LEFT JOIN projectstab p ON p.project_id=po.project_id;
ROLLBACK;

-- agent_identity_whitelist
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT key_name,key_value FROM key_values WHERE key_name IN ('Agent_Group_Id','Agent_Group_Name','Agent_Id','Agent_Name','VersionNumber','Agent_Group_Size') ORDER BY key_name;
ROLLBACK;

-- safe_numeric_operation_configuration
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT operation_id,keyname,keyvalue FROM operationpropertiestab WHERE keyname IN ('AlwaysRunSuccessOperation','chunk_size','max_number_of_threads','target_chunk_size','validate_source_text_file') AND keyvalue ~ '^[0-9]+$' ORDER BY operation_id,keyname;
ROLLBACK;

-- pending_by_definition
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT o.operation_id,o.operation_name,count(l.operation_log_id) FILTER (WHERE l.status IN (0,1,3,8,10)) active_runs,count(l.operation_log_id) retained_runs FROM operationstab o LEFT JOIN operationlogtab l ON l.operation_id=o.operation_id GROUP BY o.operation_id,o.operation_name ORDER BY o.operation_id;
ROLLBACK;

-- view_sizes
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT n.nspname schema,c.relname name,pg_get_viewdef(c.oid,true) definition FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='v' AND n.nspname='public' ORDER BY c.relname;
ROLLBACK;

-- db_connections_by_application
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT application_name,state,count(*) connections FROM pg_stat_activity WHERE datname=current_database() GROUP BY application_name,state ORDER BY application_name,state;
ROLLBACK;

-- incoming_queue_summary
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT isexecuting,msgpriority,numthreads,operationid,count(*) requests FROM incomingmsgtab GROUP BY isexecuting,msgpriority,numthreads,operationid ORDER BY operationid LIMIT 100;
ROLLBACK;

-- transformation_summaries
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT operation_summary_id,operation_instance_guid,entered_ts,source_files,target_files,source_size,target_size,source_records,target_records,total_transformation_time FROM operationsummarytab ORDER BY entered_ts DESC,operation_summary_id DESC LIMIT 100;
ROLLBACK;

-- run_progress
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT operation_progress_id,operation_instance_guid,source_file_index,number_of_source_files,percentage_done,estimated_end_time FROM operationprogresstab ORDER BY operation_progress_id DESC LIMIT 100;
ROLLBACK;

-- file_result_counters
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT operation_file_status_id,operation_id,operation_instance_guid,records,filecategory,filesize,filets FROM operationfilestatustab ORDER BY operation_file_status_id DESC LIMIT 100;
ROLLBACK;

-- instance_links
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT operation_instance_id,operation_instance_guid,entered_ts,operation_id,parent_operation_instance_guid FROM operationinstancetab ORDER BY operation_instance_id DESC LIMIT 100;
ROLLBACK;
