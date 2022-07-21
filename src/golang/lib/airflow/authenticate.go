package airflow

import (
	"context"

	"github.com/apache/airflow-client-go/airflow"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector/auth"
)

// Authenticate returns an error if the provided Airflow config is invalid.
func Authenticate(ctx context.Context, authConf auth.Config) error {
	conf, err := parseConfig(authConf)
	if err != nil {
		return err
	}

	airflowConf := airflow.NewConfiguration()
	airflowConf.Host = conf.Host
	airflowConf.Scheme = "http"
	client := airflow.NewAPIClient(airflowConf)

	cred := airflow.BasicAuth{
		UserName: conf.Username,
		Password: conf.Password,
	}
	airflowCtx := context.WithValue(ctx, airflow.ContextBasicAuth, cred)

	// Test Airflow config by listing all DAGs
	_, _, err = client.DAGApi.GetDags(airflowCtx).Execute()

	return err
}
