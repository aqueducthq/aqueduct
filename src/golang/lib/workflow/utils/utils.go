package utils

import (
	"context"
	"encoding/json"

	"github.com/aqueducthq/aqueduct/lib/collections/artifact"
	"github.com/aqueducthq/aqueduct/lib/collections/artifact_result"
	"github.com/aqueducthq/aqueduct/lib/collections/notification"
	"github.com/aqueducthq/aqueduct/lib/collections/operator"
	"github.com/aqueducthq/aqueduct/lib/collections/operator_result"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/collections/user"
	"github.com/aqueducthq/aqueduct/lib/collections/workflow"
	"github.com/aqueducthq/aqueduct/lib/collections/workflow_dag"
	"github.com/aqueducthq/aqueduct/lib/collections/workflow_dag_edge"
	"github.com/aqueducthq/aqueduct/lib/collections/workflow_dag_result"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/aqueducthq/aqueduct/lib/storage"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector/github"
	"github.com/dropbox/godropbox/errors"
	"github.com/google/uuid"
	log "github.com/sirupsen/logrus"
)

type WorkflowStoragePaths struct {
	OperatorMetadataPaths map[uuid.UUID]string
	ArtifactPaths         map[uuid.UUID]string
	ArtifactMetadataPaths map[uuid.UUID]string
}

func GenerateWorkflowStoragePaths(dag *workflow_dag.WorkflowDag) *WorkflowStoragePaths {
	workflowStoragePaths := WorkflowStoragePaths{
		OperatorMetadataPaths: make(map[uuid.UUID]string),
		ArtifactPaths:         make(map[uuid.UUID]string),
		ArtifactMetadataPaths: make(map[uuid.UUID]string),
	}

	for id := range dag.Operators {
		workflowStoragePaths.OperatorMetadataPaths[id] = uuid.New().String()
	}

	for id := range dag.Artifacts {
		workflowStoragePaths.ArtifactPaths[id] = uuid.New().String()
		workflowStoragePaths.ArtifactMetadataPaths[id] = uuid.New().String()
	}

	return &workflowStoragePaths
}

func CleanupWorkflowStorageFiles(
	ctx context.Context,
	workflowStoragePaths *WorkflowStoragePaths,
	storageConfig *shared.StorageConfig,
	metadataOnly bool,
) {
	// Clean up generated workflow storage files.
	// If `metadataOnly` is turned on, clean up only metadata files and preserve content files.
	numFiles := len(workflowStoragePaths.ArtifactMetadataPaths) + len(workflowStoragePaths.OperatorMetadataPaths)
	if !metadataOnly {
		numFiles += len(workflowStoragePaths.ArtifactPaths)
	}

	paths := make([]string, 0, numFiles)
	for _, path := range workflowStoragePaths.ArtifactMetadataPaths {
		paths = append(paths, path)
	}

	for _, path := range workflowStoragePaths.OperatorMetadataPaths {
		paths = append(paths, path)
	}

	if !metadataOnly {
		for _, path := range workflowStoragePaths.ArtifactPaths {
			paths = append(paths, path)
		}
	}

	CleanupStorageFiles(ctx, storageConfig, paths)
}

func CleanupStorageFiles(ctx context.Context, storageConfig *shared.StorageConfig, keys []string) {
	for _, key := range keys {
		err := storage.NewStorage(storageConfig).Delete(ctx, key)
		if err != nil {
			log.Errorf("Unable to clean up storage file with key: %s. %v.", key, err)
		}
	}
}

func ReadFromStorage(ctx context.Context, storageConfig *shared.StorageConfig, path string, container interface{}) error {
	// Read data from storage and deserialize payload to `container`
	serializedPayload, err := storage.NewStorage(storageConfig).Get(ctx, path)
	if err != nil {
		return errors.Wrap(err, "Unable to get object from storage")
	}

	err = json.Unmarshal(serializedPayload, container)
	if err != nil {
		return errors.Wrap(err, "Unable to unmarshal json payload to container")
	}

	return nil
}

func WriteWorkflowDagToDatabase(
	ctx context.Context,
	dag *workflow_dag.WorkflowDag,
	workflowReader workflow.Reader,
	workflowWriter workflow.Writer,
	workflowDagWriter workflow_dag.Writer,
	operatorReader operator.Reader,
	operatorWriter operator.Writer,
	workflowDagEdgeWriter workflow_dag_edge.Writer,
	artifactReader artifact.Reader,
	artifactWriter artifact.Writer,
	db database.Database,
) (uuid.UUID, error) {
	exists, err := workflowReader.Exists(ctx, dag.WorkflowId, db)
	if err != nil {
		return uuid.Nil, errors.Wrap(err, "Unable to check if the workflow already exists.")
	}

	workflowId := dag.WorkflowId
	if !exists {
		workflow, err := workflowWriter.CreateWorkflow(
			ctx,
			dag.Metadata.UserId,
			dag.Metadata.Name,
			dag.Metadata.Description,
			&dag.Metadata.Schedule,
			&dag.Metadata.RetentionPolicy,
			db,
		)
		if err != nil {
			return uuid.Nil, errors.Wrap(err, "Unable to create workflow in the database.")
		}
		workflowId = workflow.Id
	}

	workflowDag, err := workflowDagWriter.CreateWorkflowDag(
		ctx,
		workflowId,
		&dag.StorageConfig,
		&dag.EngineConfig,
		db,
	)
	if err != nil {
		return uuid.Nil, errors.Wrap(err, "Unable to create workflow dag in the database.")
	}
	dag.Id = workflowDag.Id

	localArtifactIdToDbArtifactId := make(map[uuid.UUID]uuid.UUID, len(dag.Artifacts))

	for id, artifact := range dag.Artifacts {
		exists, err := artifactReader.Exists(ctx, id, db)
		if err != nil {
			return uuid.Nil, errors.Wrap(err, "Unable to check if artifact exists in database.")
		}

		dbArtifactId := id
		if !exists {
			dbArtifact, err := artifactWriter.CreateArtifact(
				ctx,
				artifact.Name,
				artifact.Description,
				&artifact.Spec,
				db,
			)
			if err != nil {
				return uuid.Nil, errors.Wrap(err, "Unable to create artifact in the database.")
			}

			dbArtifactId = dbArtifact.Id
		}

		localArtifactIdToDbArtifactId[artifact.Id] = dbArtifactId
	}

	for id, operator := range dag.Operators {
		exists, err := operatorReader.Exists(ctx, id, db)
		if err != nil {
			return uuid.Nil, errors.Wrap(err, "Unable to check if operator exists in database.")
		}

		dbOperatorId := id
		if !exists {
			dbOperator, err := operatorWriter.CreateOperator(
				ctx,
				operator.Name,
				operator.Description,
				&operator.Spec,
				db,
			)
			if err != nil {
				return uuid.Nil, errors.Wrap(err, "Unable to create operator in the database.")
			}

			dbOperatorId = dbOperator.Id
		}

		for i, artifactId := range operator.Inputs {
			_, err = workflowDagEdgeWriter.CreateWorkflowDagEdge(
				ctx,
				workflowDag.Id,
				workflow_dag_edge.ArtifactToOperatorType,
				localArtifactIdToDbArtifactId[artifactId],
				dbOperatorId,
				int16(i), // idx
				db,
			)
			if err != nil {
				return uuid.Nil, errors.Wrap(err, "Unable to create workflow dag edge in the database.")
			}
		}

		for i, artifactId := range operator.Outputs {
			_, err = workflowDagEdgeWriter.CreateWorkflowDagEdge(
				ctx,
				workflowDag.Id,
				workflow_dag_edge.OperatorToArtifactType,
				dbOperatorId,
				localArtifactIdToDbArtifactId[artifactId],
				int16(i), // idx
				db,
			)
			if err != nil {
				return uuid.Nil, errors.Wrap(err, "Unable to create workflow dag edge in the database.")
			}
		}
	}

	return workflowId, nil
}

func ReadWorkflowDagFromDatabase(
	ctx context.Context,
	workflowDagId uuid.UUID,
	workflowReader workflow.Reader,
	workflowDagReader workflow_dag.Reader,
	operatorReader operator.Reader,
	artifactReader artifact.Reader,
	workflowDagEdgeReader workflow_dag_edge.Reader,
	db database.Database,
) (*workflow_dag.WorkflowDag, error) {
	workflowDag, err := workflowDagReader.GetWorkflowDag(ctx, workflowDagId, db)
	if err != nil {
		return nil, errors.Wrap(err, "Unable to read workflow dag from the database.")
	}

	dbWorkflow, err := workflowReader.GetWorkflow(ctx, workflowDag.WorkflowId, db)
	if err != nil {
		return nil, errors.Wrap(err, "Unable to read workflow from the database.")
	}

	workflowDag.Metadata = dbWorkflow

	workflowDag.Operators = make(map[uuid.UUID]operator.Operator)
	workflowDag.Artifacts = make(map[uuid.UUID]artifact.Artifact)

	// Populate nodes for operators and artifacts.
	operators, err := operatorReader.GetOperatorsByWorkflowDagId(ctx, workflowDag.Id, db)
	if err != nil {
		return nil, errors.Wrap(err, "Unable to read operators from the database.")
	}

	for _, op := range operators {
		// The 'Pydantic' library on the SDK expects to receive empty lists instead of nil.
		if op.Inputs == nil {
			op.Inputs = []uuid.UUID{}
		}
		if op.Outputs == nil {
			op.Outputs = []uuid.UUID{}
		}
		workflowDag.Operators[op.Id] = op
	}

	artifacts, err := artifactReader.GetArtifactsByWorkflowDagId(ctx, workflowDag.Id, db)
	if err != nil {
		return nil, errors.Wrap(err, "Unable to read artifacts from the database.")
	}

	for _, artifact := range artifacts {
		workflowDag.Artifacts[artifact.Id] = artifact
	}

	// Populate edges for operators and artifacts.
	operatorToArtifactEdges, err := workflowDagEdgeReader.GetOperatorToArtifactEdges(ctx, workflowDag.Id, db)
	if err != nil {
		return nil, errors.Wrap(err, "Unable to read operator to artifact edges from the database.")
	}

	for _, edge := range operatorToArtifactEdges {
		if operator, ok := workflowDag.Operators[edge.FromId]; ok {
			operator.Outputs = append(operator.Outputs, edge.ToId)
			workflowDag.Operators[edge.FromId] = operator
		} else {
			return nil, errors.Wrap(err, "Found a dag edge with an orphaned operator id.")
		}
	}

	artifactToOperatorEdges, err := workflowDagEdgeReader.GetArtifactToOperatorEdges(ctx, workflowDag.Id, db)
	if err != nil {
		return nil, errors.Wrap(err, "Unable to read artifact to operator edges from the database.")
	}

	for _, edge := range artifactToOperatorEdges {
		if operator, ok := workflowDag.Operators[edge.ToId]; ok {
			operator.Inputs = append(operator.Inputs, edge.FromId)
			workflowDag.Operators[edge.ToId] = operator
		} else {
			return nil, errors.Wrap(err, "Found a dag edge with an orphaned operator id.")
		}
	}

	return workflowDag, nil
}

func ReadLatestWorkflowDagFromDatabase(
	ctx context.Context,
	workflowId uuid.UUID,
	workflowReader workflow.Reader,
	workflowDagReader workflow_dag.Reader,
	operatorReader operator.Reader,
	artifactReader artifact.Reader,
	workflowDagEdgeReader workflow_dag_edge.Reader,
	db database.Database,
) (*workflow_dag.WorkflowDag, error) {
	workflowDag, err := workflowDagReader.GetLatestWorkflowDag(ctx, workflowId, db)
	if err != nil {
		return nil, errors.Wrap(err, "Unable to read the latest workflow dag from the database.")
	}

	return ReadWorkflowDagFromDatabase(
		ctx,
		workflowDag.Id,
		workflowReader,
		workflowDagReader,
		operatorReader,
		artifactReader,
		workflowDagEdgeReader,
		db,
	)
}

// This function runs 'background' update of the given workflow dag, to construct the latest version.
// For now, we only examine all github related operators and make sure we are using the latest commits.
// Any operator with newer github commits will be updated.
//
// This function updates the `workflowDag` object in-place, together with the data model updates.
// In other words, it returns the original UUID if no update happens, or the updated UUID if any part of the dag is updated.
func UpdateWorkflowDagToLatest(
	ctx context.Context,
	githubClient github.Client,
	workflowDag *workflow_dag.WorkflowDag,
	workflowReader workflow.Reader,
	workflowWriter workflow.Writer,
	workflowDagReader workflow_dag.Reader,
	workflowDagWriter workflow_dag.Writer,
	operatorReader operator.Reader,
	operatorWriter operator.Writer,
	workflowDagEdgeReader workflow_dag_edge.Reader,
	workflowDagEdgeWriter workflow_dag_edge.Writer,
	artifactReader artifact.Reader,
	artifactWriter artifact.Writer,
	db database.Database,
) (*workflow_dag.WorkflowDag, error) {
	operatorsToReplace := make([]operator.Operator, 0, len(workflowDag.Operators))
	for _, op := range workflowDag.Operators {
		opUpdated, err := github.PullOperator(
			ctx,
			githubClient,
			&op.Spec,
			&workflowDag.StorageConfig,
		)
		if err != nil {
			return nil, err
		}

		if opUpdated {
			operatorsToReplace = append(operatorsToReplace, op)
		}
	}

	// Not updated
	if len(operatorsToReplace) == 0 {
		return workflowDag, nil
	}

	// Update workflowDag object together with the data model.
	for _, op := range operatorsToReplace {
		delete(workflowDag.Operators, op.Id)
		op.Id = uuid.New()
		workflowDag.Operators[op.Id] = op
	}

	workflowId, err := WriteWorkflowDagToDatabase(
		ctx,
		workflowDag,
		workflowReader,
		workflowWriter,
		workflowDagWriter,
		operatorReader,
		operatorWriter,
		workflowDagEdgeWriter,
		artifactReader,
		artifactWriter,
		db,
	)
	if err != nil {
		return nil, err
	}

	return ReadLatestWorkflowDagFromDatabase(
		ctx,
		workflowId,
		workflowReader,
		workflowDagReader,
		operatorReader,
		artifactReader,
		workflowDagEdgeReader,
		db,
	)
}

func UpdateWorkflowDagResultMetadata(
	ctx context.Context,
	workflowDagResultId uuid.UUID,
	status shared.ExecutionStatus,
	workflowDagResultWriter workflow_dag_result.Writer,
	workflowReader workflow.Reader,
	notificationWriter notification.Writer,
	userReader user.Reader,
	db database.Database,
) {
	changes := map[string]interface{}{
		workflow_dag_result.StatusColumn: status,
	}

	_, err := workflowDagResultWriter.UpdateWorkflowDagResult(
		ctx,
		workflowDagResultId,
		changes,
		workflowReader,
		notificationWriter,
		userReader,
		db,
	)
	if err != nil {
		log.WithFields(
			log.Fields{
				"changes": changes,
			},
		).Errorf("Unable to update workflow dag result metadata: %v", err)
	}
}

// This helper function is called after executing each operator for non-preview execution.
// It pulls artifact results from storage and writes the operator and its output artifact results into the database.
// It logs any error that occurs during these steps.
func UpdateOperatorAndArtifactResults(
	ctx context.Context,
	operator *operator.Operator,
	storageConfig *shared.StorageConfig,
	operatorState *shared.ExecutionState,
	artifactMetadataPaths map[uuid.UUID]string,
	operatorToOperatorResult map[uuid.UUID]uuid.UUID,
	artifactToArtifactResult map[uuid.UUID]uuid.UUID,
	operatorResultWriter operator_result.Writer,
	artifactResultWriter artifact_result.Writer,
	db database.Database,
) {
	artifactStatuses := make(map[uuid.UUID]shared.ExecutionStatus, len(operator.Outputs))
	artifactIdToArtifactMetadata := make(map[uuid.UUID]*artifact_result.Metadata, len(operator.Outputs))
	// Initialize the map.
	for _, artifactId := range operator.Outputs {
		artifactStatuses[artifactId] = shared.FailedExecutionStatus
		artifactIdToArtifactMetadata[artifactId] = nil
	}

	if operatorState.Status == shared.SucceededExecutionStatus {
		for _, artifactId := range operator.Outputs {
			var artifactResultMetadata artifact_result.Metadata
			err := ReadFromStorage(
				ctx,
				storageConfig,
				artifactMetadataPaths[artifactId],
				&artifactResultMetadata,
			)
			if err != nil {
				log.Errorf("Unable to read artifact result metadata from storage and unmarshal: %v", err)
				continue
			}

			artifactIdToArtifactMetadata[artifactId] = &artifactResultMetadata
			artifactStatuses[artifactId] = shared.SucceededExecutionStatus
		}
	}

	updateOperatorAndArtifactResults(
		ctx,
		operator,
		operatorState,
		artifactStatuses,
		artifactIdToArtifactMetadata,
		operatorToOperatorResult,
		artifactToArtifactResult,
		operatorResultWriter,
		artifactResultWriter,
		db,
	)
}

func updateOperatorAndArtifactResults(
	ctx context.Context,
	operator *operator.Operator,
	operatorState *shared.ExecutionState,
	artifactStatuses map[uuid.UUID]shared.ExecutionStatus,
	artifactResultsMetadata map[uuid.UUID]*artifact_result.Metadata,
	operatorToOperatorResult map[uuid.UUID]uuid.UUID,
	artifactToArtifactResult map[uuid.UUID]uuid.UUID,
	operatorResultWriter operator_result.Writer,
	artifactResultWriter artifact_result.Writer,
	db database.Database,
) {
	changes := map[string]interface{}{
		operator_result.StatusColumn: operatorState.Status,
	}

	changes[operator_result.ExecStateColumn] = operatorState

	_, err := operatorResultWriter.UpdateOperatorResult(
		ctx,
		operatorToOperatorResult[operator.Id],
		changes,
		db,
	)
	if err != nil {
		log.WithFields(
			log.Fields{
				"changes": changes,
			},
		).Errorf("Unable to update operator exec state: %v", err)
	}

	// Write the artifact results.
	for _, artifactId := range operator.Outputs {
		artifactResultMap := map[string]interface{}{
			artifact_result.StatusColumn: artifactStatuses[artifactId],
		}

		if artifactResultsMetadata[artifactId] != nil {
			artifactResultMap[artifact_result.MetadataColumn] = artifactResultsMetadata[artifactId]
		}

		_, err := artifactResultWriter.UpdateArtifactResult(
			ctx,
			artifactToArtifactResult[artifactId],
			artifactResultMap,
			db,
		)
		if err != nil {
			log.WithFields(
				log.Fields{
					"changes": artifactResultMap,
				},
			).Errorf("Unable to update artifact result metadata: %v", err)
		}
	}
}
