package scheduler

import (
	"context"

	"github.com/aqueducthq/aqueduct/lib/collections/artifact"
	"github.com/aqueducthq/aqueduct/lib/collections/operator"
	"github.com/aqueducthq/aqueduct/lib/collections/operator_result"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/job"
	"github.com/aqueducthq/aqueduct/lib/vault"
	"github.com/aqueducthq/aqueduct/lib/workflow/utils"
	"github.com/dropbox/godropbox/errors"
	log "github.com/sirupsen/logrus"
)

const systemInternalErrMsg = "Aqueduct Internal Error"

var (
	ErrWrongNumInputs                = errors.New("Wrong number of operator inputs")
	ErrWrongNumOutputs               = errors.New("Wrong number of operator outputs")
	ErrWrongNumMetadataInputs        = errors.New("Wrong number of input metadata paths for operator")
	ErrWrongNumArtifactContentPaths  = errors.New("Wrong number of artifact content paths.")
	ErrWrongNumArtifactMetadataPaths = errors.New("Wrong number of artifact metadata paths.")
)

// ScheduleOperator executes an operator based on its spec.
// Inputs:
//	op: the operator to execute
//	inputs: a list of input artifacts
//	outputs: a list of output artifacts
//	artifactPaths: a pre-generated map of `artifactId -> storage paths`. It must cover all artifacts in the workflow
//	operatorMetadataPath: a pre-generated storage path to store the intermediate operator metadata.
//
// Outputs:
//	string: cron-job ID to track operator execution status.
//	error: any error that the caller should handle.
//
// Does:
// 	This function calls the corresponding executor based on the type of `spec`. It deserialize the log in
// 	the storage path as a part of the returned results. It also updates the `OperatorResult` in data model.
//
// Assumptions:
//	We use a switch to call type-specific executors for each operator type. Each type-specific executor should:
//	- Ideally managed in its own .go file under operator_execution package
//	- return (error)
//	- serialize operator metadata to `operatorMetadataPath` in json format
//	- properly deserialize input artifacts and output artifacts, based on `inputs`, `outputs`, and `artifactPaths`.
//
func ScheduleOperator(
	ctx context.Context,
	op operator.Operator,
	inputArtifacts []artifact.Artifact,
	outputArtifacts []artifact.Artifact,
	metadataPath string,
	inputContentPaths []string,
	inputMetadataPaths []string,
	outputContentPaths []string,
	outputMetadataPaths []string,
	storageConfig *shared.StorageConfig,
	jobManager job.JobManager,
	vaultObject vault.Vault,
) (string, error) {
	jobSpec, jobName, err := GenerateOperatorJobSpec(
		ctx,
		op,
		inputArtifacts,
		outputArtifacts,
		metadataPath,
		inputContentPaths,
		inputMetadataPaths,
		outputContentPaths,
		outputMetadataPaths,
		storageConfig,
		jobManager,
		vaultObject,
	)
	if err != nil {
		return "", err
	}

	if err := jobManager.Launch(ctx, jobName, jobSpec); err != nil {
		return "", errors.Wrapf(err, "unable to schedule %v", op.Spec.Type())
	}

	return jobName, nil
}

// GenerateOperatorJobSpec generates a job spec to execute the operator based
// on the specified operator spec and information about its input(s) and output(s).
// It returns a job.Spec, the job ID, and an error, if any.
func GenerateOperatorJobSpec(
	ctx context.Context,
	op operator.Operator,
	inputArtifacts []artifact.Artifact,
	outputArtifacts []artifact.Artifact,
	metadataPath string,
	inputContentPaths []string,
	inputMetadataPaths []string,
	outputContentPaths []string,
	outputMetadataPaths []string,
	storageConfig *shared.StorageConfig,
	jobManager job.JobManager,
	vaultObject vault.Vault,
) (job.Spec, string, error) {
	// Append to this switch for newly supported operator types
	if op.Spec.IsFunction() {
		// A function operator takes any number of dataframes as input and outputs
		// any number of dataframes.
		inputArtifactTypes := make([]artifact.Type, 0, len(inputArtifacts))
		for _, inputArtifact := range inputArtifacts {
			if inputArtifact.Spec.Type() != artifact.TableType && inputArtifact.Spec.Type() != artifact.JsonType {
				return nil, "", errors.New("Inputs to function operator must be Table or Parameter Artifacts.")
			}
			inputArtifactTypes = append(inputArtifactTypes, inputArtifact.Spec.Type())
		}
		outputArtifactTypes := make([]artifact.Type, 0, len(outputArtifacts))
		for _, outputArtifact := range outputArtifacts {
			if outputArtifact.Spec.Type() != artifact.TableType {
				return nil, "", errors.New("Outputs of function operator must be Table Artifacts.")
			}
			outputArtifactTypes = append(outputArtifactTypes, outputArtifact.Spec.Type())
		}

		return ScheduleFunction(
			ctx,
			*op.Spec.Function(),
			metadataPath,
			inputContentPaths,
			inputMetadataPaths,
			outputContentPaths,
			outputMetadataPaths,
			inputArtifactTypes,
			outputArtifactTypes,
			storageConfig,
			jobManager,
		)
	}

	if op.Spec.IsMetric() {
		if len(outputArtifacts) != 1 {
			return nil, "", ErrWrongNumOutputs
		}

		inputArtifactTypes := make([]artifact.Type, 0, len(inputArtifacts))
		for _, inputArtifact := range inputArtifacts {
			if inputArtifact.Spec.Type() != artifact.TableType &&
				inputArtifact.Spec.Type() != artifact.FloatType &&
				inputArtifact.Spec.Type() != artifact.JsonType {
				return nil, "", errors.New("Inputs to metric operator must be Table, Float, or Parameter Artifacts.")
			}
			inputArtifactTypes = append(inputArtifactTypes, inputArtifact.Spec.Type())
		}
		outputArtifactTypes := []artifact.Type{artifact.FloatType}

		return ScheduleFunction(
			ctx,
			op.Spec.Metric().Function,
			metadataPath,
			inputContentPaths,
			inputMetadataPaths,
			outputContentPaths,
			outputMetadataPaths,
			inputArtifactTypes,
			outputArtifactTypes,
			storageConfig,
			jobManager,
		)
	}

	if op.Spec.IsCheck() {
		if len(outputArtifacts) != 1 {
			return nil, "", ErrWrongNumOutputs
		}

		// Checks can be computed on tables and metrics.
		inputArtifactTypes := make([]artifact.Type, 0, len(inputArtifacts))
		for _, inputArtifact := range inputArtifacts {
			if inputArtifact.Spec.Type() != artifact.TableType &&
				inputArtifact.Spec.Type() != artifact.FloatType &&
				inputArtifact.Spec.Type() != artifact.JsonType {
				return nil, "", errors.New("Inputs to metric operator must be Table, Float, or Parameter Artifacts.")
			}
			inputArtifactTypes = append(inputArtifactTypes, inputArtifact.Spec.Type())
		}
		outputArtifactTypes := []artifact.Type{artifact.BoolType}

		return ScheduleFunction(
			ctx,
			op.Spec.Check().Function,
			metadataPath,
			inputContentPaths,
			inputMetadataPaths,
			outputContentPaths,
			outputMetadataPaths,
			inputArtifactTypes,
			outputArtifactTypes,
			storageConfig,
			jobManager,
		)
	}

	if op.Spec.IsExtract() {
		inputParamNames := make([]string, 0, len(inputArtifacts))
		for _, inputArtifact := range inputArtifacts {
			if inputArtifact.Spec.Type() != artifact.JsonType {
				return nil, "", errors.New("Only parameters can be used as inputs to extract operators.")
			}
			inputParamNames = append(inputParamNames, inputArtifact.Name)
		}

		if len(inputArtifacts) != 0 {
			return nil, "", ErrWrongNumInputs
		}
		if len(outputArtifacts) != 1 {
			return nil, "", ErrWrongNumOutputs
		}
		if len(outputContentPaths) != 1 {
			return nil, "", ErrWrongNumArtifactContentPaths
		}
		if len(outputMetadataPaths) != 1 {
			return nil, "", ErrWrongNumArtifactMetadataPaths
		}

		return ScheduleExtract(
			ctx,
			*op.Spec.Extract(),
			metadataPath,
			inputParamNames,
			inputContentPaths,
			inputMetadataPaths,
			outputContentPaths[0],
			outputMetadataPaths[0],
			storageConfig,
			jobManager,
			vaultObject,
		)
	}

	if op.Spec.IsLoad() {
		if len(inputArtifacts) != 1 {
			return nil, "", ErrWrongNumInputs
		}
		if len(outputArtifacts) != 0 {
			return nil, "", ErrWrongNumOutputs
		}
		if len(inputContentPaths) != 1 {
			return nil, "", ErrWrongNumArtifactContentPaths
		}
		if len(inputMetadataPaths) != 1 {
			return nil, "", ErrWrongNumArtifactMetadataPaths
		}
		return ScheduleLoad(
			ctx,
			*op.Spec.Load(),
			metadataPath,
			inputContentPaths[0],
			inputMetadataPaths[0],
			storageConfig,
			jobManager,
			vaultObject,
		)
	}

	if op.Spec.IsParam() {
		if len(inputArtifacts) != 0 {
			return nil, "", ErrWrongNumInputs
		}
		if len(outputArtifacts) != 1 {
			return nil, "", ErrWrongNumOutputs
		}
		if !outputArtifacts[0].Spec.IsJson() {
			return nil, "", errors.Newf("Internal Error: parameter must output a JSON artifact.")
		}
		if len(outputContentPaths) != 1 {
			return nil, "", ErrWrongNumArtifactContentPaths
		}
		if len(outputMetadataPaths) != 1 {
			return nil, "", ErrWrongNumArtifactMetadataPaths
		}

		return ScheduleParam(
			ctx,
			*op.Spec.Param(),
			metadataPath,
			outputContentPaths[0],
			outputMetadataPaths[0],
			storageConfig,
			jobManager,
		)
	}

	if op.Spec.IsSystemMetric() {
		if len(outputContentPaths) != 1 {
			return nil, "", ErrWrongNumArtifactContentPaths
		}
		if len(outputMetadataPaths) != 1 {
			return nil, "", ErrWrongNumArtifactMetadataPaths
		}
		// We currently allow the spec to contain multiple input_metadata paths.
		// A system metric currently spans over a single operator, so we enforce that here
		if len(inputMetadataPaths) != 1 {
			return nil, "", ErrWrongNumMetadataInputs
		}

		return ScheduleSystemMetric(
			ctx,
			*op.Spec.SystemMetric(),
			metadataPath,
			inputMetadataPaths,
			outputContentPaths[0],
			outputMetadataPaths[0],
			storageConfig,
			jobManager,
		)
	}

	// If we reach here, the operator opSpec type is not supported.
	return nil, "", errors.Newf("Unsupported operator opSpec with type %s", op.Spec.Type())
}

type FailureType int64

const (
	SystemFailure FailureType = 0
	UserFailure   FailureType = 1
	NoFailure     FailureType = 2
)

// CheckOperatorExecutionStatus returns the operator metadata (if it exists) and the operator status
// of a completed job.
func CheckOperatorExecutionStatus(
	ctx context.Context,
	jobStatus shared.ExecutionStatus,
	storageConfig *shared.StorageConfig,
	operatorMetadataPath string,
) (*operator_result.Metadata, shared.ExecutionStatus, FailureType) {
	var operatorResultMetadata operator_result.Metadata
	err := utils.ReadFromStorage(
		ctx,
		storageConfig,
		operatorMetadataPath,
		&operatorResultMetadata,
	)
	if err != nil {
		// Treat this as a system internal error since operator metadata was not found
		log.Errorf(
			"Unable to read operator metadata from storage. Operator may have failed before writing metadata. %v",
			err,
		)
		return &operator_result.Metadata{Error: systemInternalErrMsg}, shared.FailedExecutionStatus, SystemFailure
	}

	if len(operatorResultMetadata.Error) != 0 {
		// Operator wrote metadata (including an error) to storage
		return &operatorResultMetadata, shared.FailedExecutionStatus, UserFailure
	}

	if jobStatus == shared.FailedExecutionStatus {
		// Operator wrote metadata (without an error) to storage, but k8s marked the job as failed
		return &operatorResultMetadata, shared.FailedExecutionStatus, UserFailure
	}

	return &operatorResultMetadata, shared.SucceededExecutionStatus, NoFailure
}
