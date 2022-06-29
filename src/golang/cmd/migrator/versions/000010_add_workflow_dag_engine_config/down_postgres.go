package _000010_add_workflow_dag_engine_config

const downPostgresScript = `
ALTER TABLE workflow_dag
DROP COLUMN engine_config;`
