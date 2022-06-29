package orchestrator

import (
	"context"
	"time"

	"github.com/aqueducthq/aqueduct/lib/collections/artifact"
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
	"github.com/aqueducthq/aqueduct/lib/job"
	"github.com/aqueducthq/aqueduct/lib/vault"
	"github.com/aqueducthq/aqueduct/lib/workflow/scheduler"
	"github.com/aqueducthq/aqueduct/lib/workflow/utils"
	"github.com/dropbox/godropbox/errors"
	"github.com/google/uuid"
	log "github.com/sirupsen/logrus"
)

const (
	defaultTimeout = 15 * time.Minute
)

var ErrIncorrectOperatorsScheduled = errors.New("Incorrect number of operators scheduled.")

func operatorExecutionError(operators map[uuid.UUID]operator.Operator, operatorId uuid.UUID) error {
	op, ok := operators[operatorId]
	if !ok {
		return errors.Newf("Error during exeuction, invalid operator ID %s", operatorId)
	}

	return errors.Newf("Error during execution, operator ID %s, name %s", operatorId, op.Name)
}

func initializeOrchestration(
	operators map[uuid.UUID]operator.Operator,
	ready map[uuid.UUID]bool,
	operatorDependencies map[uuid.UUID]map[uuid.UUID]bool,
	artifactToDownstreamOperatorIds map[uuid.UUID][]uuid.UUID,
) {
	// This block does an initial scan of all operators and set the initial state for the orchestration.
	// Input data structures should be empty and will be updated throughout initialization:
	// - set upstream artifact counts for all operators
	// - put all operators without any upstream to 'ready to schedule' set
	// - set downstream operator list for all artifacts
	for id, operator := range operators {
		operatorDependencies[id] = make(map[uuid.UUID]bool, len(operator.Inputs))
		for _, artifactId := range operator.Inputs {
			operatorDependencies[id][artifactId] = true
		}

		if len(operator.Inputs) == 0 {
			ready[id] = true
		}

		for _, artifactId := range operator.Inputs {
			downstreamOps, ok := artifactToDownstreamOperatorIds[artifactId]
			if !ok {
				downstreamOps = make([]uuid.UUID, 0, len(operators))
				artifactToDownstreamOperatorIds[artifactId] = downstreamOps
			}

			artifactToDownstreamOperatorIds[artifactId] = append(downstreamOps, id)
		}
	}
}

// `updateCompletedOp` checks the status of actively running operators and updates
// their status according to the execution result. It returns a bool indicating
// whether the workflow execution should stop due to an error in the user code, and
// any internal system error occurred during the execution.
func updateCompletedOp(
	ctx context.Context,
	operators map[uuid.UUID]operator.Operator,
	ready map[uuid.UUID]bool,
	active map[uuid.UUID]bool,
	operatorDependencies map[uuid.UUID]map[uuid.UUID]bool,
	artifactToDownstreamOperatorIds map[uuid.UUID][]uuid.UUID,
	operatorIdToJobId map[uuid.UUID]string,
	storageConfig *shared.StorageConfig,
	artifactMetadataPaths map[uuid.UUID]string,
	operatorMetadataPaths map[uuid.UUID]string,
	operatorToOperatorResult map[uuid.UUID]uuid.UUID,
	artifactToArtifactResult map[uuid.UUID]uuid.UUID,
	operatorResultWriter operator_result.Writer,
	artifactResultWriter artifact_result.Writer,
	db database.Database,
	jobManager job.JobManager,
	isPreview bool,
) (bool, error) {
	completedIds := make([]uuid.UUID, 0, len(active))
	for id := range active {
		jobStatus, err := jobManager.Poll(ctx, operatorIdToJobId[id])
		if err != nil {
			return false, err
		}

		if jobStatus != shared.PendingExecutionStatus {
			op, ok := operators[id]
			if !ok {
				return false, operatorExecutionError(operators, id)
			}

			operatorResultMetadata, operatorStatus, failureType := scheduler.CheckOperatorExecutionStatus(
				ctx,
				jobStatus,
				storageConfig,
				operatorMetadataPaths[op.Id],
			)

			if !isPreview {
				utils.UpdateOperatorAndArtifactResults(
					ctx,
					&op,
					storageConfig,
					operatorStatus,
					operatorResultMetadata,
					artifactMetadataPaths,
					operatorToOperatorResult,
					artifactToArtifactResult,
					operatorResultWriter,
					artifactResultWriter,
					db,
				)
			}

			if operatorStatus == shared.FailedExecutionStatus && failureType == scheduler.SystemFailure {
				return false, operatorExecutionError(operators, id)
			}

			if operatorStatus == shared.FailedExecutionStatus && failureType == scheduler.UserFailure {
				// There is an user error when executing the operator.
				return true, nil
			}

			completedIds = append(completedIds, id)

			for _, artifactId := range op.Outputs {
				if downstreampOps, ok := artifactToDownstreamOperatorIds[artifactId]; ok {
					for _, downstreamOpId := range downstreampOps {
						if _, ok := operatorDependencies[downstreamOpId][artifactId]; !ok {
							return false, operatorExecutionError(operators, downstreamOpId)
						}

						delete(operatorDependencies[downstreamOpId], artifactId)
						if len(operatorDependencies[downstreamOpId]) == 0 {
							ready[downstreamOpId] = true
						}
					}
				}
			}
		}
	}

	for _, id := range completedIds {
		delete(active, id)
	}

	return false, nil
}

func scheduleOperators(
	ctx context.Context,
	operators map[uuid.UUID]operator.Operator,
	artifacts map[uuid.UUID]artifact.Artifact,
	ready map[uuid.UUID]bool,
	active map[uuid.UUID]bool,
	operatorIdToJobId map[uuid.UUID]string,
	storageConfig *shared.StorageConfig,
	artifactContentPaths map[uuid.UUID]string,
	artifactMetadataPaths map[uuid.UUID]string,
	operatorMetadataPaths map[uuid.UUID]string,
	jobManager job.JobManager,
	vaultObject vault.Vault,
) error {
	for id := range ready {
		op, ok := operators[id]
		if !ok {
			return operatorExecutionError(operators, id)
		}

		operatorMetadataPath, ok := operatorMetadataPaths[id]
		if !ok {
			return operatorExecutionError(operators, id)
		}

		inputArtifacts := make([]artifact.Artifact, 0, len(op.Inputs))
		inputContentPaths := make([]string, 0, len(op.Inputs))
		inputMetadataPaths := make([]string, 0, len(op.Inputs))
		for _, inputArtifactId := range op.Inputs {
			inputArtifact, ok := artifacts[inputArtifactId]
			if !ok {
				return errors.Newf("Cannot find artifact with ID %v", inputArtifactId)
			}

			inputArtifacts = append(inputArtifacts, inputArtifact)
			inputContentPaths = append(inputContentPaths, artifactContentPaths[inputArtifact.Id])
			inputMetadataPaths = append(inputMetadataPaths, artifactMetadataPaths[inputArtifact.Id])
		}

		outputArtifacts := make([]artifact.Artifact, 0, len(op.Outputs))
		outputContentPaths := make([]string, 0, len(op.Outputs))
		outputMetadataPaths := make([]string, 0, len(op.Outputs))
		for _, outputArtifactId := range op.Outputs {
			outputArtifact, ok := artifacts[outputArtifactId]
			if !ok {
				return errors.Newf("Cannot find artifact with ID %v", outputArtifactId)
			}

			outputArtifacts = append(outputArtifacts, outputArtifact)
			outputContentPaths = append(outputContentPaths, artifactContentPaths[outputArtifact.Id])
			outputMetadataPaths = append(outputMetadataPaths, artifactMetadataPaths[outputArtifact.Id])
		}

		jobId, err := scheduler.ScheduleOperator(
			ctx,
			op,
			inputArtifacts,
			outputArtifacts,
			operatorMetadataPath,
			inputContentPaths,
			inputMetadataPaths,
			outputContentPaths,
			outputMetadataPaths,
			storageConfig,
			jobManager,
			vaultObject,
		)
		if err != nil {
			return err
		}

		active[id] = true
		operatorIdToJobId[id] = jobId
	}

	return nil
}

// `waitForActiveOperators` is deferred till the end of `Orchestrate`.
// If the workflow is successfully executed, this should return immediately
// as `active` would be empty. But if the workflow failed in the middle,
// there may be some in-progress operators that we want to wait till they finish.
// After they finish, we can then perform cleanup operations such as clearing
// storage files.
func waitForActiveOperators(
	ctx context.Context,
	active map[uuid.UUID]bool,
	operatorIdToJobId map[uuid.UUID]string,
	jobManager job.JobManager,
) {
	for len(active) != 0 {
		completedIds := make([]uuid.UUID, 0, len(active))
		for id := range active {
			jobStatus, err := jobManager.Poll(ctx, operatorIdToJobId[id])
			if err != nil {
				// If the err is job doesn't exist, then it means it already finished and was garbage-collected.
				if err != job.ErrJobNotExist {
					log.Errorf(
						"Unexpected error occurred when checking the job status during failed workflow cleanup. %v",
						err,
					)
					return
				}
			}

			if jobStatus != shared.PendingExecutionStatus {
				completedIds = append(completedIds, id)
			}
		}

		for _, id := range completedIds {
			delete(active, id)
		}
	}
}

func Preview(
	ctx context.Context,
	dag *workflow_dag.WorkflowDag,
	workflowStoragePaths *utils.WorkflowStoragePaths,
	pollIntervalMillisec time.Duration,
	jobManager job.JobManager,
	vaultObject vault.Vault,
) (shared.ExecutionStatus, error) {
	return orchestrate(
		ctx,
		dag,
		workflowStoragePaths,
		pollIntervalMillisec,
		workflow.NewNoopReader(true),
		workflow_dag_result.NewNoopWriter(true),
		operator_result.NewNoopWriter(true),
		artifact_result.NewNoopWriter(true),
		notification.NewNoopWriter(true),
		user.NewNoopReader(true),
		database.NewNoopDatabase(),
		jobManager,
		vaultObject,
		true,
	)
}

func Execute(
	ctx context.Context,
	dag *workflow_dag.WorkflowDag,
	workflowStoragePaths *utils.WorkflowStoragePaths,
	pollIntervalMillisec time.Duration,
	workflowReader workflow.Reader,
	workflowDagResultWriter workflow_dag_result.Writer,
	operatorResultWriter operator_result.Writer,
	artifactResultWriter artifact_result.Writer,
	notificationWriter notification.Writer,
	userReader user.Reader,
	db database.Database,
	jobManager job.JobManager,
	vaultObject vault.Vault,
) (shared.ExecutionStatus, error) {
	return orchestrate(
		ctx,
		dag,
		workflowStoragePaths,
		pollIntervalMillisec,
		workflowReader,
		workflowDagResultWriter,
		operatorResultWriter,
		artifactResultWriter,
		notificationWriter,
		userReader,
		db,
		jobManager,
		vaultObject,
		false,
	)
}

func orchestrate(
	ctx context.Context,
	dag *workflow_dag.WorkflowDag,
	workflowStoragePaths *utils.WorkflowStoragePaths,
	pollIntervalMillisec time.Duration,
	workflowReader workflow.Reader,
	workflowDagResultWriter workflow_dag_result.Writer,
	operatorResultWriter operator_result.Writer,
	artifactResultWriter artifact_result.Writer,
	notificationWriter notification.Writer,
	userReader user.Reader,
	db database.Database,
	jobManager job.JobManager,
	vaultObject vault.Vault,
	isPreview bool,
) (shared.ExecutionStatus, error) {
	numOperators := len(dag.Operators)
	artifactToDownstreamOperatorIds := make(map[uuid.UUID][]uuid.UUID, len(dag.Artifacts))
	operatorIdToJobId := make(map[uuid.UUID]string, numOperators)
	// Maps from operator ID to its upstream artifact dependencies.
	operatorDependencies := make(map[uuid.UUID]map[uuid.UUID]bool, numOperators)
	ready := make(map[uuid.UUID]bool, numOperators)
	active := make(map[uuid.UUID]bool, numOperators)

	defer func() {
		waitForActiveOperators(ctx, active, operatorIdToJobId, jobManager)
	}()

	initializeOrchestration(
		dag.Operators,
		ready,
		operatorDependencies,
		artifactToDownstreamOperatorIds,
	)

	status := shared.FailedExecutionStatus

	// These are only relevant for non-preview execution.
	var workflowDagResultId uuid.UUID
	operatorToOperatorResult := make(map[uuid.UUID]uuid.UUID, len(dag.Operators))
	artifactToArtifactResult := make(map[uuid.UUID]uuid.UUID, len(dag.Artifacts))

	if !isPreview {
		// First, we create a database record of workflow dag result and set its status to `pending`.
		// TODO: wrap these writes into a transaction.
		// eng-599-adding-transaction-support-to-our-database-reader-and-writer
		workflowDagResult, err := workflowDagResultWriter.CreateWorkflowDagResult(ctx, dag.Id, db)
		if err != nil {
			return shared.FailedExecutionStatus, errors.Wrap(err, "Unable to create workflow dag result record.")
		}

		workflowDagResultId = workflowDagResult.Id

		defer func() {
			// We `defer` this call to ensure that the WorkflowDagResult metadata is always updated.
			utils.UpdateWorkflowDagResultMetadata(
				ctx,
				workflowDagResultId,
				status,
				workflowDagResultWriter,
				workflowReader,
				notificationWriter,
				userReader,
				db,
			)
		}()

		// Initialize all operator results and artifact results.
		for operatorId := range dag.Operators {
			operatorResult, err := operatorResultWriter.CreateOperatorResult(
				ctx,
				workflowDagResultId,
				operatorId,
				db,
			)
			if err != nil {
				return shared.FailedExecutionStatus, errors.Wrap(err, "Failed to create operator result record.")
			}

			operatorToOperatorResult[operatorId] = operatorResult.Id
		}

		for artifactId := range dag.Artifacts {
			storagePath := workflowStoragePaths.ArtifactPaths[artifactId]
			artifactResult, err := artifactResultWriter.CreateArtifactResult(
				ctx,
				workflowDagResultId,
				artifactId,
				storagePath,
				db,
			)
			if err != nil {
				return shared.FailedExecutionStatus, errors.Wrap(err, "Failed to create artifact result record.")
			}

			artifactToArtifactResult[artifactId] = artifactResult.Id
		}
	}

	start := time.Now()

	// We keep orchestrating while there's any active or ready-to-schedule operators.
	// While such case, we do the following:
	// - poll the state of all active operators
	// - if any operator is completed, we:
	//   - for each of output artifacts, decrement their downstream operators' 'upstream artifact' count by 1
	//   - if any operator's upstream count become 0, mark it as 'ready'
	// - remove all completed operator from the list of active ones
	// - schedule all operators in ready list
	//   - mark each of them as active
	//   - clear the ready list after all operators are scheduled
	for len(ready) > 0 || len(active) > 0 {
		if time.Since(start) > defaultTimeout {
			return shared.FailedExecutionStatus, errors.New("Reached timeout waiting for workflow to complete.")
		}

		stopWorkflowExecution, err := updateCompletedOp(
			ctx,
			dag.Operators,
			ready,
			active,
			operatorDependencies,
			artifactToDownstreamOperatorIds,
			operatorIdToJobId,
			&dag.StorageConfig,
			workflowStoragePaths.ArtifactMetadataPaths,
			workflowStoragePaths.OperatorMetadataPaths,
			operatorToOperatorResult,
			artifactToArtifactResult,
			operatorResultWriter,
			artifactResultWriter,
			db,
			jobManager,
			isPreview,
		)
		if err != nil {
			// There is an internal error in our system.
			return shared.FailedExecutionStatus, err
		}

		if stopWorkflowExecution {
			// There is an error in the user code.
			return shared.FailedExecutionStatus, nil
		}

		// Schedule all operators in ready state.
		err = scheduleOperators(
			ctx,
			dag.Operators,
			dag.Artifacts,
			ready,
			active,
			operatorIdToJobId,
			&dag.StorageConfig,
			workflowStoragePaths.ArtifactPaths,
			workflowStoragePaths.ArtifactMetadataPaths,
			workflowStoragePaths.OperatorMetadataPaths,
			jobManager,
			vaultObject,
		)
		if err != nil {
			return shared.FailedExecutionStatus, err
		}

		ready = map[uuid.UUID]bool{}

		time.Sleep(pollIntervalMillisec)
	}

	status = shared.SucceededExecutionStatus

	return status, nil
}
