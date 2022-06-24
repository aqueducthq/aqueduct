package airflow

import (
	"encoding/json"

	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector/auth"
)

type config struct {
	host     string
	username string
	password string
}

// parseConfig takes in an auth.Config and parses into a config struct.
// It also returns an error, if any.
func parseConfig(conf auth.Config) (*config, error) {
	data, err := conf.Marshal()
	if err != nil {
		return nil, err
	}

	var c config
	if err := json.Unmarshal(data, &c); err != nil {
		return nil, err
	}

	return &c, nil
}
