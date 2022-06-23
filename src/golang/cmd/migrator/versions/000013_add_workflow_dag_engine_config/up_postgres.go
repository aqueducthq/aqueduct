package _000013_add_workflow_dag_engine_config

const upPostgresScript = `
ALTER TABLE workflow_dag
ADD COLUMN engine_config JSONB NOT NULL
DEFAULT '{"type":"aqueduct", "aqueductConfig":{}}'::jsonb;`
