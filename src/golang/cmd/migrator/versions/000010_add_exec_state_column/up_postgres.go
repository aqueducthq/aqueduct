package _000010_add_exec_state_column

const upPostgresScript = `
ALTER TABLE operator_result
ADD COLUMN execution_state JSONB;
`
