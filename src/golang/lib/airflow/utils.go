package airflow

import (
	"net/http"
	"strings"

	"github.com/dropbox/godropbox/errors"
)

// generateDagId generates an Airflow DAG ID for a workflow.
func generateDagId(workflowName string) string {
	return strings.ReplaceAll(workflowName, " ", "_")
}

// generateTaskId generates an Airflow task ID for an operator.
func generateTaskId(operatorName string) string {
	return strings.ReplaceAll(operatorName, " ", "_")
}

// wrapApiErrors wraps an error from the Airflow API using the error returned
// and the HTTP response.
func wrapApiError(err error, api string, resp *http.Response) error {
	return errors.Wrapf(err, "Airflow %v error with status: %v", api, resp.Status)
}
