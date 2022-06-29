package airflow

import (
	"fmt"
	"net/http"

	"github.com/dropbox/godropbox/errors"
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

// wrapApiErrors wraps an error from the Airflow API using the error returned
// and the HTTP response.
func wrapApiError(err error, api string, resp *http.Response) error {
	return errors.Wrapf(err, "Airflow %v error with status: %v", api, resp.Status)
}
