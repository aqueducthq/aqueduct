package airflow

import (
	"strings"
)

// generateDagId generates an Airflow DAG ID for a workflow.
func generateDagId(workflowName string) string {
	return strings.ReplaceAll(workflowName, " ", "_")
}

// generateTaskId generates an Airflow task ID for an operator.
func generateTaskId(operatorName string) string {
	return strings.ReplaceAll(operatorName, " ", "_")
}
