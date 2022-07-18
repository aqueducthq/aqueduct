package shared

import (
	"database/sql/driver"

	"github.com/aqueducthq/aqueduct/lib/collections/utils"
	"github.com/google/uuid"
)

type EngineType string

const (
	AqueductEngineType EngineType = "aqueduct"
	AirflowEngineType  EngineType = "airflow"
)

type EngineConfig struct {
	Type           EngineType      `yaml:"type" json:"type"`
	AqueductConfig *AqueductConfig `yaml:"aqueductConfig" json:"aqueduct_config,omitempty"`
	AirflowConfig  *AirflowConfig  `yaml:"airflowConfig" json:"airflow_config,omitempty"`
}

type AqueductConfig struct{}

type AirflowConfig struct {
	IntegrationId              uuid.UUID
	DagId                      string
	OperatorToTask             map[uuid.UUID]string
	OperatorMetadataPathPrefix map[uuid.UUID]string
	ArtifactContentPathPrefix  map[uuid.UUID]string
	ArtifactMetadataPathPrefix map[uuid.UUID]string
}

func (e *EngineConfig) Scan(value interface{}) error {
	return utils.ScanJsonB(value, e)
}

func (e *EngineConfig) Value() (driver.Value, error) {
	return utils.ValueJsonB(*e)
}
