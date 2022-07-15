package airflow

import (
	"context"

	"github.com/apache/airflow-client-go/airflow"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector/auth"
)

type client struct {
	apiClient *airflow.APIClient
	ctx       context.Context
}

func newClient(ctx context.Context, authConf auth.Config) (*client, error) {
	conf, err := parseConfig(authConf)
	if err != nil {
		return nil, err
	}

	airflowConf := airflow.NewConfiguration()
	airflowConf.Host = conf.Host
	airflowConf.Scheme = "http"

	apiClient := airflow.NewAPIClient(airflowConf)

	cred := airflow.BasicAuth{
		UserName: conf.Username,
		Password: conf.Password,
	}

	airflowCtx := context.WithValue(ctx, airflow.ContextBasicAuth, cred)

	return &client{
		apiClient: apiClient,
		ctx:       airflowCtx,
	}, nil
}
