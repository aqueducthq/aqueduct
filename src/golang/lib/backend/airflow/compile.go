package airflow

import "context"

// CompileToDag takes in a WorkflowDag and generates a Python file
// that defines the equivalent Airflow DAG. It returns the Python file and
// an error, if any.
func CompileToDag(
	ctx context.Context,
) ([]byte, error) {
	return nil, nil
}
