package shared

import (
	"database/sql/driver"

	"github.com/aqueducthq/aqueduct/lib/collections/utils"
	"github.com/google/uuid"
)

type RuntimeType string

const (
	AqueductRuntimeType RuntimeType = "aqueduct"
	AirflowRuntimeType  RuntimeType = "airflow"
)

type RuntimeConfig struct {
	Type       RuntimeType `yaml:"type" json:"type"`
	S3Config   *S3Config   `yaml:"s3Config" json:"s3_config,omitempty"`
	FileConfig *FileConfig `yaml:"fileConfig" json:"file_config,omitempty"`
}

type AqueductConfig struct{}

type AirflowConfig struct {
	DagId           string
	OperatorToTask  map[uuid.UUID]string
	StoragePrefixes map[uuid.UUID]string
}

func (r *RuntimeConfig) Scan(value interface{}) error {
	return utils.ScanJsonB(value, r)
}

func (r *RuntimeConfig) Value() (driver.Value, error) {
	return utils.ValueJsonB(*r)
}
