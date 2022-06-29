package workflow_dag

import (
	"context"
	"time"

	"github.com/aqueducthq/aqueduct/lib/collections/artifact"
	"github.com/aqueducthq/aqueduct/lib/collections/operator"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/collections/workflow"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/google/uuid"
)

type WorkflowDag struct {
	Id            uuid.UUID            `db:"id" json:"id"`
	WorkflowId    uuid.UUID            `db:"workflow_id" json:"workflow_id"`
	CreatedAt     time.Time            `db:"created_at" json:"created_at"`
	StorageConfig shared.StorageConfig `db:"storage_config" json:"storage_config"`
	EngineConfig  shared.EngineConfig  `db:"engine_config" json:"engine_config"`

	/* Field not stored in DB */
	Metadata  *workflow.Workflow              `json:"metadata"`
	Operators map[uuid.UUID]operator.Operator `json:"operators,omitempty"`
	Artifacts map[uuid.UUID]artifact.Artifact `json:"artifacts,omitempty"`
}

func (dag *WorkflowDag) GetOperatorByName(name string) *operator.Operator {
	for _, op := range dag.Operators {
		if op.Name == name {
			return &op
		}
	}
	return nil
}

type Reader interface {
	GetWorkflowDag(ctx context.Context, id uuid.UUID, db database.Database) (*WorkflowDag, error)
	GetWorkflowDags(ctx context.Context, ids []uuid.UUID, db database.Database) ([]WorkflowDag, error)
	GetLatestWorkflowDag(ctx context.Context, workflowId uuid.UUID, db database.Database) (*WorkflowDag, error)
	GetWorkflowDagsByWorkflowId(
		ctx context.Context,
		workflowId uuid.UUID,
		db database.Database,
	) ([]WorkflowDag, error)
	GetWorkflowDagByWorkflowDagResultId(
		ctx context.Context,
		workflowDagResultId uuid.UUID,
		db database.Database,
	) (*WorkflowDag, error)
	GetWorkflowDagsByOperatorId(
		ctx context.Context,
		operatorId uuid.UUID,
		db database.Database,
	) ([]WorkflowDag, error)
}

type Writer interface {
	CreateWorkflowDag(
		ctx context.Context,
		workflowId uuid.UUID,
		storageConfig *shared.StorageConfig,
		runtimeConfig *shared.EngineConfig,
		db database.Database,
	) (*WorkflowDag, error)
	UpdateWorkflowDag(
		ctx context.Context,
		id uuid.UUID,
		changes map[string]interface{},
		db database.Database,
	) (*WorkflowDag, error)
	DeleteWorkflowDag(ctx context.Context, id uuid.UUID, db database.Database) error
	DeleteWorkflowDags(ctx context.Context, ids []uuid.UUID, db database.Database) error
}

func NewReader(dbConf *database.DatabaseConfig) (Reader, error) {
	if dbConf.Type == database.PostgresType {
		return newPostgresReader(), nil
	}

	if dbConf.Type == database.SqliteType {
		return newSqliteReader(), nil
	}

	return nil, database.ErrUnsupportedDbType
}

func NewWriter(dbConf *database.DatabaseConfig) (Writer, error) {
	if dbConf.Type == database.PostgresType {
		return newPostgresWriter(), nil
	}

	if dbConf.Type == database.SqliteType {
		return newSqliteWriter(), nil
	}

	return nil, database.ErrUnsupportedDbType
}
