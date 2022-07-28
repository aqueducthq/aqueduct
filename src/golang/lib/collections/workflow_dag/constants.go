package workflow_dag

import (
	"fmt"
	"strings"
)

const (
	tableName = "workflow_dag"

	// WorkflowDag table column names
	IdColumn            = "id"
	WorkflowIdColumn    = "workflow_id"
	CreatedAtColumn     = "created_at"
	StorageConfigColumn = "storage_config"
	EngineConfigColumn  = "engine_config"
)

// Returns a joined string of all WorkflowDag columns.
func allColumns() string {
	return strings.Join(
		[]string{
			IdColumn,
			WorkflowIdColumn,
			CreatedAtColumn,
			StorageConfigColumn,
			EngineConfigColumn,
		},
		",",
	)
}

// Returns a joined string of all WorkflowDag columns prefixed by table name.
func allColumnsWithPrefix() string {
	return strings.Join(
		[]string{
			fmt.Sprintf("%s.%s", tableName, IdColumn),
			fmt.Sprintf("%s.%s", tableName, WorkflowIdColumn),
			fmt.Sprintf("%s.%s", tableName, CreatedAtColumn),
			fmt.Sprintf("%s.%s", tableName, StorageConfigColumn),
			fmt.Sprintf("%s.%s", tableName, EngineConfigColumn),
		},
		",",
	)
}
