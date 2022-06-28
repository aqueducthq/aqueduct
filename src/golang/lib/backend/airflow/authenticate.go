package airflow

import (
	"context"

	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector/auth"
)

// Authenticate returns an error if the provided Airflow config is invalid.
func Authenticate(ctx context.Context, authConf auth.Config) error {
	cli, err := newClient(ctx, authConf)
	if err != nil {
		return err
	}

	// Test Airflow config by listing all DAGs
	_, _, err = cli.apiClient.DAGApi.GetDags(cli.ctx).Execute()

	return err
}
