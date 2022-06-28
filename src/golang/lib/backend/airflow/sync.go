package airflow

import (
	"context"

	"github.com/apache/airflow-client-go/airflow"
	"github.com/aqueducthq/aqueduct/lib/collections/artifact_result"
	"github.com/aqueducthq/aqueduct/lib/collections/notification"
	"github.com/aqueducthq/aqueduct/lib/collections/operator_result"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/collections/user"
	"github.com/aqueducthq/aqueduct/lib/collections/workflow"
	"github.com/aqueducthq/aqueduct/lib/collections/workflow_dag"
	"github.com/aqueducthq/aqueduct/lib/collections/workflow_dag_result"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector/auth"
	"github.com/aqueducthq/aqueduct/lib/workflow/utils"
	"github.com/dropbox/godropbox/errors"
	"github.com/google/uuid"
)

// SyncWorkflows syncs all workflows using an Airflow engine with any new
// Airflow dag runs since the last sync. It returns an error, if any.
func SyncWorkflows(
	ctx context.Context,
	db database.Database,
) error {
	return nil
}

// syncWorkflowDag fetches the latest workflow runs for the workflow dag
// specified from Airflow and updates the database accordingly with the results.
// It returns an error, if any.
func syncWorkflowDag(
	ctx context.Context,
	dag *workflow_dag.WorkflowDag,
) error {
	authConf, err := auth.ReadConfigFromSecret(ctx, dag.RuntimeConfig.AirflowConfig.IntegrationId, nil)
	if err != nil {
		return err
	}

	cli, err := newClient(ctx, authConf)
	if err != nil {
		return err
	}

	dagsResp, resp, err := cli.apiClient.DAGRunApi.GetDagRuns(cli.ctx, dag.RuntimeConfig.AirflowConfig.DagId).Execute()
	if err != nil {
		return err
	}

	for _, dagRun := range *dagsResp.DagRuns {
		// TODO
	}

	return nil
}

func createWorkflowDagResult(
	ctx context.Context,
	cli *client,
	dag *workflow_dag.WorkflowDag,
	run *airflow.DAGRun,
	workflowDagResultWriter workflow_dag_result.Writer,
	operatorResultWriter operator_result.Writer,
	artifactResultWriter artifact_result.Writer,
	notificationWriter notification.Writer,
	workflowReader workflow.Reader,
	userReader user.Reader,
	db database.Database,
) error {
	var workflowDagStatus shared.ExecutionStatus
	switch *run.State {
	case airflow.DAGSTATE_SUCCESS:
		workflowDagStatus = shared.SucceededExecutionStatus
	case airflow.DAGSTATE_FAILED:
		workflowDagStatus = shared.FailedExecutionStatus
	default:
		// Do not create WorkflowDagResult for Airflow DAG runs that have not finished
		return nil
	}

	workflowDagResult, err := workflowDagResultWriter.CreateWorkflowDagResult(ctx, dag.Id, db)
	if err != nil {
		return err
	}

	// TODO: Consider merging this UPDATE with CREATE above
	changes := map[string]interface{}{
		workflow_dag_result.CreatedAtColumn: *run.StartDate.Get(),
		workflow_dag_result.StatusColumn:    workflowDagStatus,
	}

	if _, err := workflowDagResultWriter.UpdateWorkflowDagResult(
		ctx,
		workflowDagResult.Id,
		changes,
		workflowReader,
		notificationWriter,
		userReader,
		db,
	); err != nil {
		return err
	}

	taskResp, resp, err := cli.apiClient.TaskInstanceApi.GetTaskInstances(
		cli.ctx,
		dag.RuntimeConfig.AirflowConfig.DagId,
		*run.DagRunId.Get(),
	).Execute()
	if err != nil {
		return errors.Wrapf(err, "Airflow TaskInstanceAPI error with status: %v", resp.Status)
	}

	taskIdToInstance := make(map[string]*airflow.TaskInstance, len(*taskResp.TaskInstances))
	for _, task := range *taskResp.TaskInstances {
		taskIdToInstance[*task.TaskId] = &task
	}

	for _, op := range dag.Operators {
		taskId, ok := dag.RuntimeConfig.AirflowConfig.OperatorToTask[op.Id]
		if !ok {
			return errors.Newf("Unable to find Airflow task ID for operator %v", op.Id)
		}

		task, ok := taskIdToInstance[taskId]
		if !ok {
			return errors.Newf("Unable to find Airflow task %v", taskId)
		}

		// Initialize OperatorResult
		operatorResult, err := operatorResultWriter.CreateOperatorResult(
			ctx,
			workflowDagResult.Id,
			op.Id,
			db,
		)
		if err != nil {
			return err
		}

		// Initialize ArtifactResult(s) for this operator's output artifact(s)
		artifactToResult := make(map[uuid.UUID]*artifact_result.ArtifactResult, len(op.Outputs))
		for _, artifactId := range op.Outputs {
			artifact, ok := dag.Artifacts[artifactId]
			if !ok {
				return errors.Newf("Unable to find artifact %v", artifactId)
			}

			contentPath, ok := dag.RuntimeConfig.AirflowConfig.ArtifactContentPathPrefix[artifact.Id]
			if !ok {
				return errors.Newf("Unable to find content path for artifact %v", artifact.Id)
			}

			artifactResult, err := artifactResultWriter.CreateArtifactResult(
				ctx,
				workflowDagResult.Id,
				artifact.Id,
				contentPath,
				db,
			)
			if err != nil {
				return err
			}

			artifactToResult[artifactId] = artifactResult
		}

		if *task.State != airflow.TASKSTATE_FAILED || *task.State != airflow.TASKSTATE_SUCCESS {
			// The Airflow task never completed, so we leave the operator and downstream artifacts
			// in the pending state.
			continue
		}

		operatorMetadataPath, ok := dag.RuntimeConfig.AirflowConfig.OperatorMetadataPathPrefix[op.Id]
		if !ok {
			return errors.Newf("Unable to find metadata path for operator %v", op.Id)
		}

		// Check operator metadata to determine operator status
		var operatorResultMetadata operator_result.Metadata
		if err := utils.ReadFromStorage(
			ctx,
			&dag.StorageConfig,
			operatorMetadataPath,
			&operatorResultMetadata,
		); err != nil {
			return err
		}

		operatorStatus := shared.FailedExecutionStatus
		if len(operatorResultMetadata.Error) == 0 && *task.State == airflow.TASKSTATE_SUCCESS {
			operatorStatus = shared.SucceededExecutionStatus
		}

		// Update OperatorResult status
		changes := map[string]interface{}{
			operator_result.StatusColumn:   operatorStatus,
			operator_result.MetadataColumn: &operatorResultMetadata,
		}
		if _, err := operatorResultWriter.UpdateOperatorResult(
			ctx,
			operatorResult.Id,
			changes,
			db,
		); err != nil {
			return err
		}

		// Update ArtifactResult statuses
		artifactStatus := operatorStatus
		for artifactId, artifactResult := range artifactToResult {
			artifactMetadataPath, ok := dag.RuntimeConfig.AirflowConfig.ArtifactMetadataPathPrefix[artifactId]
			if !ok {
				return errors.Newf("Unable to find metadata path for artifact %v", artifactId)
			}

			var artifactResultMetadata artifact_result.Metadata
			if err := utils.ReadFromStorage(
				ctx,
				&dag.StorageConfig,
				artifactMetadataPath,
				&artifactResultMetadata,
			); err != nil {
				return err
			}

			changes := map[string]interface{}{
				artifact_result.StatusColumn:   artifactStatus,
				artifact_result.MetadataColumn: &artifactResultMetadata,
			}
			if _, err := artifactResultWriter.UpdateArtifactResult(
				ctx,
				artifactResult.Id,
				changes,
				db,
			); err != nil {
				return err
			}
		}
	}

	return nil
}
