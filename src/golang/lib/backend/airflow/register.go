package airflow

import (
	"context"
	"fmt"
	"time"

	"github.com/aqueducthq/aqueduct/lib/collections/artifact"
	"github.com/aqueducthq/aqueduct/lib/collections/operator_result"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/collections/workflow_dag"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/aqueducthq/aqueduct/lib/job"
	"github.com/aqueducthq/aqueduct/lib/storage"
	"github.com/aqueducthq/aqueduct/lib/vault"
	"github.com/aqueducthq/aqueduct/lib/workflow/scheduler"
	"github.com/aqueducthq/aqueduct/lib/workflow/utils"
	"github.com/dropbox/godropbox/errors"
	"github.com/google/uuid"
)

const (
	pollCompileAirflowInterval = 500 * time.Millisecond
	pollCompileAirflowTimeout  = 30 * time.Second
)

// RegisterWorkflow registers a workflow with an Airflow backend.
// It returns the Airflow DAG Python spec file and an error, if any.
//
// Assumptions:
//   - All of the in-memory fields of `dag` are set.
//   - All of the in-memory fields of each Operator in `dag.Operators` are set.
func RegisterWorkflow(
	ctx context.Context,
	dag *workflow_dag.WorkflowDag,
	storageConfig *shared.StorageConfig,
	jobManager job.JobManager,
	vault vault.Vault,
	db database.Database,
	workflowDagWriter workflow_dag.Writer,
) ([]byte, error) {
	dagId := generateDagId(dag.Metadata.Name, dag.WorkflowId)

	operatorToTask := make(map[uuid.UUID]string, len(dag.Operators))

	// Generate storage path prefixes for operator metadata, artifact content,
	// and artifact metadata. At runtime, the Airflow DAG run ID is appended to
	// the relevant path prefix to form a unique storage path without requiring
	// coordination between Airflow and the Aqueduct server.
	storagePathPrefixes := utils.GenerateWorkflowStoragePaths(dag)
	operatorToMetadataPathPrefix := storagePathPrefixes.OperatorMetadataPaths
	artifactToContentPathPrefix := storagePathPrefixes.ArtifactPaths
	artifactToMetadataPathPrefix := storagePathPrefixes.ArtifactMetadataPaths

	taskToJobSpec := make(map[string]job.Spec, len(dag.Operators))
	// Generate job spec for each Airflow task
	for _, op := range dag.Operators {
		inputArtifactSpecs := make([]artifact.Spec, 0, len(op.Inputs))
		inputContentPathPrefixes := make([]string, 0, len(op.Inputs))
		inputMetadataPathPrefixes := make([]string, 0, len(op.Inputs))
		for _, artifactId := range op.Inputs {
			input, ok := dag.Artifacts[artifactId]
			if !ok {
				return nil, errors.Newf("cannot find artifact with ID %v", artifactId)
			}

			inputArtifactSpecs = append(inputArtifactSpecs, input.Spec)
			inputContentPathPrefixes = append(inputContentPathPrefixes, artifactToContentPathPrefix[input.Id])
			inputMetadataPathPrefixes = append(inputMetadataPathPrefixes, artifactToMetadataPathPrefix[input.Id])
		}

		outputArtifactSpecs := make([]artifact.Spec, 0, len(op.Outputs))
		outputContentPathPrefixes := make([]string, 0, len(op.Outputs))
		outputMetadataPathPrefixes := make([]string, 0, len(op.Outputs))
		for _, artifactId := range op.Outputs {
			output, ok := dag.Artifacts[artifactId]
			if !ok {
				return nil, errors.Newf("cannot find artifact with ID %v", artifactId)
			}

			outputArtifactSpecs = append(outputArtifactSpecs, output.Spec)
			outputContentPathPrefixes = append(outputContentPathPrefixes, artifactToContentPathPrefix[output.Id])
			outputMetadataPathPrefixes = append(outputMetadataPathPrefixes, artifactToMetadataPathPrefix[output.Id])
		}

		jobSpec, err := scheduler.GenerateOperatorJobSpec(
			ctx,
			op.Spec,
			inputArtifactSpecs,
			outputArtifactSpecs,
			operatorToMetadataPathPrefix[op.Id],
			inputContentPathPrefixes,
			inputMetadataPathPrefixes,
			outputContentPathPrefixes,
			outputMetadataPathPrefixes,
			storageConfig,
			jobManager,
			vault,
		)
		if err != nil {
			return nil, err
		}

		taskId := generateTaskId(op.Name, op.Id)

		operatorToTask[op.Id] = taskId
		taskToJobSpec[taskId] = jobSpec
	}

	operatorMetadataPath := fmt.Sprintf("compile-airflow-metadata-%s", uuid.New().String())
	operatorOutputPath := fmt.Sprintf("compile-airflow-output-%s", uuid.New().String())

	defer func() {
		go utils.CleanupStorageFiles(ctx, storageConfig, []string{operatorMetadataPath, operatorOutputPath})
	}()

	jobName := fmt.Sprintf("compile-airflow-operator-%s", uuid.New().String())
	jobSpec := job.NewCompileAirflowSpec(
		jobName,
		storageConfig,
		operatorMetadataPath,
		operatorOutputPath,
		dagId,
		taskToJobSpec,
		nil,
	)

	if err := jobManager.Launch(ctx, jobSpec.Name(), jobSpec); err != nil {
		return nil, err
	}

	jobStatus, err := job.PollJob(ctx, jobSpec.Name(), jobManager, pollCompileAirflowInterval, pollCompileAirflowTimeout)
	if err != nil {
		return nil, err
	}

	if jobStatus == shared.FailedExecutionStatus {
		return nil, errors.New("Compile Airflow job failed.")
	}

	var metadata operator_result.Metadata
	if err := utils.ReadFromStorage(
		ctx,
		storageConfig,
		operatorMetadataPath,
		&metadata,
	); err != nil {
		return nil, err
	}

	if len(metadata.Error) > 0 {
		return nil, errors.Newf("Compile Airflow job failed: %v", metadata.Error)
	}

	airflowDagFile, err := storage.NewStorage(storageConfig).Get(ctx, operatorOutputPath)
	if err != nil {
		return nil, err
	}

	// Update the AirflowRuntimeConfig for `dag`
	newRuntimeConfig := dag.RuntimeConfig
	newRuntimeConfig.AirflowConfig.OperatorToTask = operatorToTask
	newRuntimeConfig.AirflowConfig.OperatorMetadataPathPrefix = operatorToMetadataPathPrefix
	newRuntimeConfig.AirflowConfig.ArtifactContentPathPrefix = artifactToContentPathPrefix
	newRuntimeConfig.AirflowConfig.ArtifactMetadataPathPrefix = artifactToMetadataPathPrefix

	_, err = workflowDagWriter.UpdateWorkflowDag(
		ctx,
		dag.Id,
		map[string]interface{}{
			workflow_dag.RuntimeConfigColumn: &newRuntimeConfig,
		},
		db,
	)
	if err != nil {
		return nil, err
	}

	return airflowDagFile, nil
}
