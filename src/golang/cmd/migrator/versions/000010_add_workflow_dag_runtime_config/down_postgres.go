package _000010_add_workflow_dag_runtime_config

const downPostgresScript = `
ALTER TABLE workflow_dag
DROP COLUMN runtime_config;`
