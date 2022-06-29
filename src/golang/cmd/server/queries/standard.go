package queries

import (
	"context"
	"fmt"

	"github.com/aqueducthq/aqueduct/lib/collections/operator"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/aqueducthq/aqueduct/lib/database/stmt_preparers"
	"github.com/dropbox/godropbox/errors"
	"github.com/google/uuid"
)

type standardReaderImpl struct{}

func (r *standardReaderImpl) GetLoadOperatorSpecByOrganization(
	ctx context.Context,
	organizationId string,
	db database.Database,
) ([]LoadOperatorSpecResponse, error) {
	query := fmt.Sprintf(
		`SELECT DISTINCT workflow_dag_edge.from_id AS artifact_id, artifact.name AS artifact_name, operator.id AS load_operator_id, workflow.name AS workflow_name, workflow.id AS workflow_id, operator.spec 
		 FROM app_user, workflow, workflow_dag, workflow_dag_edge, operator, artifact
		 WHERE app_user.id = workflow.user_id AND workflow.id = workflow_dag.workflow_id AND 
		 workflow_dag.id = workflow_dag_edge.workflow_dag_id AND workflow_dag_edge.to_id = operator.id AND 
		 artifact.id = workflow_dag_edge.from_id AND
		 operator.spec->>'type' = '%s' AND app_user.organization_id = $1;`,
		operator.LoadType,
	)

	var response []LoadOperatorSpecResponse
	err := db.Query(ctx, &response, query, organizationId)
	return response, err
}

func (r *standardReaderImpl) GetLatestWorkflowDagIdsByOrganizationId(
	ctx context.Context,
	organizationId string,
	db database.Database,
) ([]WorkflowDagId, error) {
	query := `
		 SELECT workflow_dag.id FROM workflow_dag WHERE created_at IN (
		 SELECT MAX(workflow_dag.created_at) FROM app_user, workflow, workflow_dag 
		 WHERE app_user.id = workflow.user_id AND workflow.id = workflow_dag.workflow_id AND 
		 app_user.organization_id = $1 
		 GROUP BY workflow.id);`

	var workflowDags []WorkflowDagId
	err := db.Query(ctx, &workflowDags, query, organizationId)
	return workflowDags, err
}

func (r *standardReaderImpl) GetArtifactIdsFromWorkflowDagIdsAndDownstreamOperatorIds(
	ctx context.Context,
	operatorIds []uuid.UUID,
	workflowDagIds []uuid.UUID,
	db database.Database,
) ([]ArtifactId, error) {
	if len(workflowDagIds) == 0 || len(operatorIds) == 0 {
		return nil, errors.New("Provided empty IDs list.")
	}

	query := fmt.Sprintf(
		`SELECT DISTINCT from_id AS artifact_id FROM workflow_dag_edge WHERE workflow_dag_id IN (%s) 
		 AND to_id IN (%s);`,
		stmt_preparers.GenerateArgsList(len(workflowDagIds), 1),
		stmt_preparers.GenerateArgsList(len(operatorIds), len(workflowDagIds)+1),
	)

	args := stmt_preparers.CastIdsListToInterfaceList(workflowDagIds)
	args = append(args, stmt_preparers.CastIdsListToInterfaceList(operatorIds)...)

	var result []ArtifactId
	err := db.Query(ctx, &result, query, args...)
	return result, err
}

func (r *standardReaderImpl) GetArtifactResultsByArtifactIds(
	ctx context.Context,
	artifactIds []uuid.UUID,
	db database.Database,
) ([]ArtifactResponse, error) {
	if len(artifactIds) == 0 {
		return nil, errors.New("Provided empty IDs list.")
	}

	query := fmt.Sprintf(
		`SELECT artifact_result.artifact_id, artifact_result.workflow_dag_result_id, artifact_result.status, workflow_dag_result.created_at AS timestamp 
		 FROM artifact_result, workflow_dag_result 
		 WHERE artifact_result.workflow_dag_result_id = workflow_dag_result.id AND 
		 artifact_result.artifact_id IN (%s);`,
		stmt_preparers.GenerateArgsList(len(artifactIds), 1),
	)

	args := stmt_preparers.CastIdsListToInterfaceList(artifactIds)

	var response []ArtifactResponse
	err := db.Query(ctx, &response, query, args...)
	return response, err
}

func (r *standardReaderImpl) GetCheckResultsByArtifactIds(
	ctx context.Context,
	artifactIds []uuid.UUID,
	db database.Database,
) ([]ArtifactCheckResponse, error) {
	if len(artifactIds) == 0 {
		return nil, errors.New("Provided empty IDs list.")
	}

	query := fmt.Sprintf(
		`SELECT DISTINCT workflow_dag_edge.from_id AS artifact_id, operator.name AS name, operator_result.status, 
		 operator_result.metadata, operator_result.workflow_dag_result_id 
		 FROM workflow_dag_edge, operator, operator_result 
		 WHERE workflow_dag_edge.to_id = operator.id AND operator.id = operator_result.operator_id AND 
		 workflow_dag_edge.from_id IN (%s) AND operator.spec->>'type' = '%s';`,
		stmt_preparers.GenerateArgsList(len(artifactIds), 1),
		operator.CheckType,
	)

	args := stmt_preparers.CastIdsListToInterfaceList(artifactIds)

	var response []ArtifactCheckResponse
	err := db.Query(ctx, &response, query, args...)
	return response, err
}

func (r *standardReaderImpl) GetOperatorResultsByArtifactIdsAndWorkflowDagResultIds(
	ctx context.Context,
	artifactIds, workflowDagResultIds []uuid.UUID,
	db database.Database,
) ([]ArtifactOperatorResponse, error) {
	if len(artifactIds) == 0 || len(workflowDagResultIds) == 0 {
		return nil, errors.New("Provided empty IDs list.")
	}

	query := fmt.Sprintf(
		`SELECT DISTINCT workflow_dag_edge.to_id AS artifact_id, operator_result.metadata, operator_result.workflow_dag_result_id  
		 FROM workflow_dag_edge, operator_result 
		 WHERE workflow_dag_edge.from_id = operator_result.operator_id AND workflow_dag_edge.to_id IN (%s) AND 
		 operator_result.workflow_dag_result_id IN (%s);`,
		stmt_preparers.GenerateArgsList(len(artifactIds), 1),
		stmt_preparers.GenerateArgsList(len(workflowDagResultIds), len(artifactIds)+1),
	)

	args := stmt_preparers.CastIdsListToInterfaceList(artifactIds)
	args = append(args, stmt_preparers.CastIdsListToInterfaceList(workflowDagResultIds)...)

	var response []ArtifactOperatorResponse
	err := db.Query(ctx, &response, query, args...)
	return response, err
}

func (r *standardReaderImpl) GetWorkflowLastRun(
	ctx context.Context,
	db database.Database,
) ([]WorkflowLastRunResponse, error) {
	query := `
		SELECT workflow.id AS workflow_id, workflow.schedule, workflow_dag_result.created_at AS last_run_at 
		FROM workflow, workflow_dag, workflow_dag_result, 
		(SELECT workflow.id, MAX(workflow_dag_result.created_at) AS created_at 
		FROM workflow, workflow_dag, workflow_dag_result 
		WHERE workflow.id = workflow_dag.workflow_id AND workflow_dag.id = workflow_dag_result.workflow_dag_id 
		GROUP BY workflow.id) AS workflow_latest_run 
		WHERE workflow.id = workflow_dag.workflow_id AND workflow_dag.id = workflow_dag_result.workflow_dag_id 
		AND workflow.id = workflow_latest_run.id AND workflow_dag_result.created_at = workflow_latest_run.created_at;`

	var response []WorkflowLastRunResponse

	err := db.Query(ctx, &response, query)
	return response, err
}
