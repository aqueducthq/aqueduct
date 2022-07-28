package airflow

import (
	"encoding/json"

	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector/auth"
)

type config struct {
	Host                 string `json:"host"  yaml:"host"`
	Username             string `json:"username"  yaml:"username"`
	Password             string `json:"password"  yaml:"password"`
	S3CredentialsPath    string `json:"s3_credentials_path"  yaml:"s3CredentialsPath"`
	S3CredentialsProfile string `json:"s3_credentials_profile"  yaml:"s3CredentialsProfile"`
}

// parseConfig takes in an auth.Config and parses into a config.
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
