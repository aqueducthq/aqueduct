package _000010_add_workflow_dag_engine_config

const sqliteScript = `
ALTER TABLE workflow_dag
ADD COLUMN engine_config BLOB
DEFAULT '{"type":"aqueduct", "aqueductConfig":{}}'
NOT NULL;
`
