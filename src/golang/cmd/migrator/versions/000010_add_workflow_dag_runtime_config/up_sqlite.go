package _000010_add_workflow_dag_runtime_config

const sqliteScript = `
ALTER TABLE workflow_dag
ADD COLUMN runtime_config BLOB
DEFAULT '{"type":"aqueduct", "aqueductConfig":{}}'
NOT NULL;
`
