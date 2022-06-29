package airflow

import (
	"context"

	"github.com/apache/airflow-client-go/airflow"
	"github.com/aqueducthq/aqueduct/lib/collections/artifact_result"
	"github.com/aqueducthq/aqueduct/lib/collections/notification"
	"github.com/aqueducthq/aqueduct/lib/collections/operator"
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
	log "github.com/sirupsen/logrus"
)

// SyncWorkflows syncs all workflows using an Airflow engine with any new
// Airflow dag runs since the last sync. It returns an error, if any.
func SyncWorkflows(
	ctx context.Context,
	workflowReader workflow.Reader,
	workflowDagReader workflow_dag.Reader,
	workflowDagResultWriter workflow_dag_result.Writer,
	operatorResultWriter operator_result.Writer,
	artifactResultWriter artifact_result.Writer,
	notificationWriter notification.Writer,
	userReader user.Reader,
	db database.Database,
) error {
	// Read all workflows where the latest DAG is for an Airflow engine
	var dags []workflow_dag.WorkflowDag
	// Invoke sync on them

	for _, dag := range dags {
		if err := syncWorkflowDag(
			ctx,
			&dag,
			workflowReader,
			workflowDagReader,
			workflowDagResultWriter,
			operatorResultWriter,
			artifactResultWriter,
			notificationWriter,
			userReader,
			db,
		); err != nil {
			log.Errorf("Unable to sync with Airflow for WorkflowDag %v", dag.Id)
		}
	}

	return nil
}

// syncWorkflowDag fetches the latest workflow runs for the workflow dag
// specified from Airflow and updates the database accordingly with the results.
// It returns an error, if any.
func syncWorkflowDag(
	ctx context.Context,
	dag *workflow_dag.WorkflowDag,
	workflowReader workflow.Reader,
	workflowDagReader workflow_dag.Reader,
	workflowDagResultWriter workflow_dag_result.Writer,
	operatorResultWriter operator_result.Writer,
	artifactResultWriter artifact_result.Writer,
	notificationWriter notification.Writer,
	userReader user.Reader,
	db database.Database,
) error {
	authConf, err := auth.ReadConfigFromSecret(ctx, dag.RuntimeConfig.AirflowConfig.IntegrationId, nil)
	if err != nil {
		return err
	}

	cli, err := newClient(ctx, authConf)
	if err != nil {
		return err
	}

	dagRunsResp, resp, err := cli.apiClient.DAGRunApi.GetDagRuns(cli.ctx, dag.RuntimeConfig.AirflowConfig.DagId).Execute()
	if err != nil {
		return wrapApiError(err, "GetDagRuns", resp)
	}

	txn, err := db.BeginTx(ctx)
	if err != nil {
		return err
	}
	defer database.TxnRollbackIgnoreErr(ctx, txn)

	for _, dagRun := range *dagRunsResp.DagRuns {
		if *dagRun.State != airflow.DAGSTATE_SUCCESS && *dagRun.State != airflow.DAGSTATE_FAILED {
			continue
		}

		if err := syncWorkflowDagResult(
			ctx,
			cli,
			dag,
			&dagRun,
			workflowReader,
			workflowDagReader,
			workflowDagResultWriter,
			operatorResultWriter,
			artifactResultWriter,
			notificationWriter,
			userReader,
			txn,
		); err != nil {
			return err
		}
	}

	if err := txn.Commit(ctx); err != nil {
		return err
	}

	return nil
}

func syncWorkflowDagResult(
	ctx context.Context,
	cli *client,
	dag *workflow_dag.WorkflowDag,
	run *airflow.DAGRun,
	workflowReader workflow.Reader,
	workflowDagReader workflow_dag.Reader,
	workflowDagResultWriter workflow_dag_result.Writer,
	operatorResultWriter operator_result.Writer,
	artifactResultWriter artifact_result.Writer,
	notificationWriter notification.Writer,
	userReader user.Reader,
	db database.Database,
) error {
	taskIdToInstance, err := getDagRunTaskInstances(
		cli,
		dag.RuntimeConfig.AirflowConfig.DagId,
		*run.DagRunId.Get(),
	)
	if err != nil {
		return err
	}

	workflowDagResult, err := createWorkflowDagResult(
		ctx,
		dag,
		run,
		workflowReader,
		workflowDagResultWriter,
		operatorResultWriter,
		artifactResultWriter,
		notificationWriter,
		userReader,
		db,
	)
	if err != nil {
		return err
	}

	for _, op := range dag.Operators {
		if err := createOperatorResult(
			ctx,
			dag,
			&op,
			workflowDagResult.Id,
			taskIdToInstance,
			operatorResultWriter,
			artifactResultWriter,
			db,
		); err != nil {
			return err
		}
	}

	return nil
}

func getDagRunTaskInstances(
	cli *client,
	dagId string,
	dagRunId string,
) (map[string]*airflow.TaskInstance, error) {
	taskResp, resp, err := cli.apiClient.TaskInstanceApi.GetTaskInstances(
		cli.ctx,
		dagId,
		dagRunId,
	).Execute()
	if err != nil {
		return nil, errors.Wrapf(err, "Airflow TaskInstanceAPI error with status: %v", resp.Status)
	}

	taskIdToInstance := make(map[string]*airflow.TaskInstance, len(*taskResp.TaskInstances))
	for _, task := range *taskResp.TaskInstances {
		taskIdToInstance[*task.TaskId] = &task
	}

	return taskIdToInstance, nil
}

func createWorkflowDagResult(
	ctx context.Context,
	dag *workflow_dag.WorkflowDag,
	run *airflow.DAGRun,
	workflowReader workflow.Reader,
	workflowDagResultWriter workflow_dag_result.Writer,
	operatorResultWriter operator_result.Writer,
	artifactResultWriter artifact_result.Writer,
	notificationWriter notification.Writer,
	userReader user.Reader,
	db database.Database,
) (*workflow_dag_result.WorkflowDagResult, error) {
	var workflowDagStatus shared.ExecutionStatus
	switch *run.State {
	case airflow.DAGSTATE_SUCCESS:
		workflowDagStatus = shared.SucceededExecutionStatus
	case airflow.DAGSTATE_FAILED:
		workflowDagStatus = shared.FailedExecutionStatus
	default:
		// Do not create WorkflowDagResult for Airflow DAG runs that have not finished
		return nil, errors.New("Cannot create WorkflowDagResult for in progress Airflow DAG.")
	}

	workflowDagResult, err := workflowDagResultWriter.CreateWorkflowDagResult(ctx, dag.Id, db)
	if err != nil {
		return nil, err
	}

	// TODO: Consider merging this UPDATE with CREATE above
	changes := map[string]interface{}{
		workflow_dag_result.CreatedAtColumn: *run.StartDate.Get(),
		workflow_dag_result.StatusColumn:    workflowDagStatus,
	}

	return workflowDagResultWriter.UpdateWorkflowDagResult(
		ctx,
		workflowDagResult.Id,
		changes,
		workflowReader,
		notificationWriter,
		userReader,
		db,
	)
}

func createOperatorResult(
	ctx context.Context,
	dag *workflow_dag.WorkflowDag,
	op *operator.Operator,
	workflowDagResultId uuid.UUID,
	taskIdToInstance map[string]*airflow.TaskInstance,
	operatorResultWriter operator_result.Writer,
	artifactResultWriter artifact_result.Writer,
	db database.Database,
) error {
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
		workflowDagResultId,
		op.Id,
		db,
	)
	if err != nil {
		return err
	}

	// Initialize ArtifactResult(s) for this operator's output artifact(s)
	artifactResults := make([]*artifact_result.ArtifactResult, 0, len(op.Outputs))
	for _, artifactId := range op.Outputs {
		artifactResult, err := createArtifactResult(
			ctx,
			dag,
			artifactId,
			workflowDagResultId,
			artifactResultWriter,
			db,
		)
		if err != nil {
			return err
		}

		artifactResults = append(artifactResults, artifactResult)
	}

	if *task.State != airflow.TASKSTATE_FAILED && *task.State != airflow.TASKSTATE_SUCCESS {
		// The Airflow task never completed, so we leave the operator and its output artifacts
		// in the pending state.
		return nil
	}

	// Update OperatorResult status
	operatorStatus, err := updateOperatorResultStatus(
		ctx,
		dag,
		operatorResult,
		*task.State,
		operatorResultWriter,
		db,
	)
	if err != nil {
		return err
	}

	// Update ArtifactResult statuses
	for _, artifactResult := range artifactResults {
		if err := updateArtifactResult(
			ctx,
			dag,
			artifactResult,
			operatorStatus,
			artifactResultWriter,
			db,
		); err != nil {
			return err
		}
	}

	return nil
}

func createArtifactResult(
	ctx context.Context,
	dag *workflow_dag.WorkflowDag,
	artifactId uuid.UUID,
	workflowDagResultId uuid.UUID,
	artifactResultWriter artifact_result.Writer,
	db database.Database,
) (*artifact_result.ArtifactResult, error) {
	artifact, ok := dag.Artifacts[artifactId]
	if !ok {
		return nil, errors.Newf("Unable to find artifact %v", artifactId)
	}

	contentPath, ok := dag.RuntimeConfig.AirflowConfig.ArtifactContentPathPrefix[artifact.Id]
	if !ok {
		return nil, errors.Newf("Unable to find content path for artifact %v", artifact.Id)
	}

	return artifactResultWriter.CreateArtifactResult(
		ctx,
		workflowDagResultId,
		artifact.Id,
		contentPath,
		db,
	)
}

func updateOperatorResultStatus(
	ctx context.Context,
	dag *workflow_dag.WorkflowDag,
	operatorResult *operator_result.OperatorResult,
	taskState airflow.TaskState,
	operatorResultWriter operator_result.Writer,
	db database.Database,
) (shared.ExecutionStatus, error) {
	operatorMetadataPath, ok := dag.RuntimeConfig.AirflowConfig.OperatorMetadataPathPrefix[operatorResult.OperatorId]
	if !ok {
		return shared.FailedExecutionStatus, errors.Newf("Unable to find metadata path for operator %v", operatorResult.OperatorId)
	}

	// Check operator metadata to determine operator status
	var operatorResultMetadata operator_result.Metadata
	if err := utils.ReadFromStorage(
		ctx,
		&dag.StorageConfig,
		operatorMetadataPath,
		&operatorResultMetadata,
	); err != nil {
		return shared.FailedExecutionStatus, err
	}

	operatorStatus := shared.FailedExecutionStatus
	if len(operatorResultMetadata.Error) == 0 && taskState == airflow.TASKSTATE_SUCCESS {
		// An operator is considered successful if the Airflow task was successful
		// and no execution error is found in the operator metadata written to storage.
		operatorStatus = shared.SucceededExecutionStatus
	}

	// Update OperatorResult status
	changes := map[string]interface{}{
		operator_result.StatusColumn:   operatorStatus,
		operator_result.MetadataColumn: &operatorResultMetadata,
	}
	_, err := operatorResultWriter.UpdateOperatorResult(
		ctx,
		operatorResult.Id,
		changes,
		db,
	)

	return operatorStatus, err
}

func updateArtifactResult(
	ctx context.Context,
	dag *workflow_dag.WorkflowDag,
	artifactResult *artifact_result.ArtifactResult,
	artifactStatus shared.ExecutionStatus,
	artifactResultWriter artifact_result.Writer,
	db database.Database,
) error {
	artifactMetadataPath, ok := dag.RuntimeConfig.AirflowConfig.ArtifactMetadataPathPrefix[artifactResult.ArtifactId]
	if !ok {
		return errors.Newf("Unable to find metadata path for artifact %v", artifactResult.ArtifactId)
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
	_, err := artifactResultWriter.UpdateArtifactResult(
		ctx,
		artifactResult.Id,
		changes,
		db,
	)

	return err
}
