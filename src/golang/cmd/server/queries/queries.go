package queries

import (
	"context"
	"time"

	"github.com/aqueducthq/aqueduct/lib/collections/operator"
	"github.com/aqueducthq/aqueduct/lib/collections/operator_result"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/collections/workflow"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/google/uuid"
)

type LoadOperatorSpecResponse struct {
	ArtifactId     uuid.UUID     `db:"artifact_id" json:"artifact_id"`
	ArtifactName   string        `db:"artifact_name" json:"artifact_name"`
	LoadOperatorId uuid.UUID     `db:"load_operator_id" json:"load_operator_id"`
	WorkflowName   string        `db:"workflow_name" json:"workflow_name"`
	WorkflowId     uuid.UUID     `db:"workflow_id" json:"workflow_id"`
	Spec           operator.Spec `db:"spec" json:"spec"`
}

type WorkflowDagId struct {
	Id uuid.UUID `db:"id" json:"id"`
}

type ArtifactId struct {
	ArtifactId uuid.UUID `db:"artifact_id" json:"artifact_id"`
}

type ArtifactResponse struct {
	ArtifactId          uuid.UUID              `db:"artifact_id" json:"artifact_id"`
	WorkflowDagResultId uuid.UUID              `db:"workflow_dag_result_id" json:"workflow_dag_result_id"`
	Status              shared.ExecutionStatus `db:"status" json:"status"`
	Timestamp           time.Time              `db:"timestamp" json:"timestamp"`
}
type ArtifactCheckResponse struct {
	ArtifactId          uuid.UUID                `db:"artifact_id" json:"artifact_id"`
	WorkflowDagResultId uuid.UUID                `db:"workflow_dag_result_id" json:"workflow_dag_result_id"`
	Status              shared.ExecutionStatus   `db:"status" json:"status"`
	Name                string                   `db:"name" json:"name"`
	Metadata            operator_result.Metadata `db:"metadata" json:"metadata"`
}

type ArtifactOperatorResponse struct {
	ArtifactId          uuid.UUID                `db:"artifact_id" json:"artifact_id"`
	Metadata            operator_result.Metadata `db:"metadata" json:"metadata"`
	WorkflowDagResultId uuid.UUID                `db:"workflow_dag_result_id" json:"workflow_dag_result_id"`
}

type WorkflowLastRunResponse struct {
	WorkflowId uuid.UUID         `db:"workflow_id" json:"workflow_id"`
	Schedule   workflow.Schedule `db:"schedule" json:"schedule"`
	LastRunAt  time.Time         `db:"last_run_at" json:"last_run_at"`
}

type Reader interface {
	GetLoadOperatorSpecByOrganization(
		ctx context.Context,
		organizationId string,
		db database.Database,
	) ([]LoadOperatorSpecResponse, error)
	GetLatestWorkflowDagIdsByOrganizationId(
		ctx context.Context,
		organizationId string,
		db database.Database,
	) ([]WorkflowDagId, error)
	GetArtifactIdsFromWorkflowDagIdsAndDownstreamOperatorIds(
		ctx context.Context,
		operatorIds []uuid.UUID,
		workflowDagIds []uuid.UUID,
		db database.Database,
	) ([]ArtifactId, error)
	GetArtifactResultsByArtifactIds(
		ctx context.Context,
		artifactIds []uuid.UUID,
		db database.Database,
	) ([]ArtifactResponse, error)
	GetCheckResultsByArtifactIds(
		ctx context.Context,
		artifactIds []uuid.UUID,
		db database.Database,
	) ([]ArtifactCheckResponse, error)
	GetOperatorResultsByArtifactIdsAndWorkflowDagResultIds(
		ctx context.Context,
		artifactIds, workflowDagResultIds []uuid.UUID,
		db database.Database,
	) ([]ArtifactOperatorResponse, error)
	GetWorkflowLastRun(
		ctx context.Context,
		db database.Database,
	) ([]WorkflowLastRunResponse, error)
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
