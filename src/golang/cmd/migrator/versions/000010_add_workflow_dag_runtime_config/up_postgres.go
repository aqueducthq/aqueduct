package _000010_add_workflow_dag_runtime_config

const upPostgresScript = `
ALTER TABLE workflow_dag
ADD COLUMN runtime_config JSONB NOT NULL
DEFAULT '{"type":"aqueduct", "aqueductConfig":{}}'::jsonb;`