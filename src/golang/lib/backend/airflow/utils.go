package airflow

import (
	"fmt"

	"github.com/google/uuid"
)

// generateDagId generates an Airflow DAG ID for a workflow.
func generateDagId(workflowName string, workflowId uuid.UUID) string {
	return fmt.Sprintf("%s-%s", workflowName, workflowId)
}

// generateTaskId generates an Airflow task ID for an operator.
func generateTaskId(operatorName string, operatorId uuid.UUID) string {
	return fmt.Sprintf("%s-%s", operatorName, operatorId)
}
