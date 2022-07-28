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
	IntegrationId              uuid.UUID            `json:"integration_id"  yaml:"integration_id"`
	DagId                      string               `json:"dag_id"  yaml:"dag_id"`
	OperatorToTask             map[uuid.UUID]string `json:"operator_to_task"  yaml:"operator_to_task"`
	OperatorMetadataPathPrefix map[uuid.UUID]string `json:"operator_metadata_path_prefix"  yaml:"operator_metadata_path_prefix"`
	ArtifactContentPathPrefix  map[uuid.UUID]string `json:"artifact_content_path_prefix"  yaml:"artifact_content_path_prefix"`
	ArtifactMetadataPathPrefix map[uuid.UUID]string `json:"artifact_metadata_path_prefix"  yaml:"artifact_metadata_path_prefix"`
}

func (e *EngineConfig) Scan(value interface{}) error {
	return utils.ScanJsonB(value, e)
}

func (e *EngineConfig) Value() (driver.Value, error) {
	return utils.ValueJsonB(*e)
}
