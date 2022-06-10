package scheduler

import (
	"context"
	"fmt"

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
	ErrWrongNumArtifactContentPaths  = errors.New("Wrong number of artifact content paths.")
	ErrWrongNumArtifactMetadataPaths = errors.New("Wrong number of artifact metadata paths.")
)

// ScheduleOperator executes an operator based on its spec.
// Inputs:
//	spec: the operator spec consisting its type, and more metadata based on the type
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
	opSpec operator.Spec,
	inputArtifactSpecs []artifact.Spec,
	outputArtifactSpecs []artifact.Spec,
	metadataPath string,
	inputContentPaths []string,
	inputMetadataPaths []string,
	outputContentPaths []string,
	outputMetadataPaths []string,
	storageConfig *shared.StorageConfig,
	jobManager job.JobManager,
	vaultObject vault.Vault,
) (string, error) {
	fmt.Println("THERE ARE THE PATHS WE LEAD")
	fmt.Println(outputMetadataPaths)
	// Append to this switch for newly supported operator types
	if opSpec.IsFunction() {
		// A function operator takes any number of dataframes as input and outputs
		// any number of dataframes.
		inputArtifactTypes := make([]artifact.Type, 0, len(inputArtifactSpecs))
		for _, inputArtifactSpec := range inputArtifactSpecs {
			if inputArtifactSpec.Type() != artifact.TableType && inputArtifactSpec.Type() != artifact.JsonType {
				return "", errors.New("Inputs to function operator must be Table or Parameter Artifacts.")
			}
			inputArtifactTypes = append(inputArtifactTypes, inputArtifactSpec.Type())
		}
		outputArtifactTypes := make([]artifact.Type, 0, len(outputArtifactSpecs))
		for _, outputArtifactSpec := range outputArtifactSpecs {
			if outputArtifactSpec.Type() != artifact.TableType {
				return "", errors.New("Outputs of function operator must be Table Artifacts.")
			}
			outputArtifactTypes = append(outputArtifactTypes, outputArtifactSpec.Type())
		}

		return ScheduleFunction(
			ctx,
			*opSpec.Function(),
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

	if opSpec.IsMetric() {
		if len(outputArtifactSpecs) != 1 {
			return "", ErrWrongNumOutputs
		}

		inputArtifactTypes := make([]artifact.Type, 0, len(inputArtifactSpecs))
		for _, inputArtifactSpec := range inputArtifactSpecs {
			if inputArtifactSpec.Type() != artifact.TableType &&
				inputArtifactSpec.Type() != artifact.FloatType &&
				inputArtifactSpec.Type() != artifact.JsonType {
				return "", errors.New("Inputs to metric operator must be Table, Float, or Parameter Artifacts.")
			}
			inputArtifactTypes = append(inputArtifactTypes, inputArtifactSpec.Type())
		}
		outputArtifactTypes := []artifact.Type{artifact.FloatType}

		return ScheduleFunction(
			ctx,
			opSpec.Metric().Function,
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

	if opSpec.IsCheck() {
		if len(outputArtifactSpecs) != 1 {
			return "", ErrWrongNumOutputs
		}

		// Checks can be computed on tables and metrics.
		inputArtifactTypes := make([]artifact.Type, 0, len(inputArtifactSpecs))
		for _, inputArtifactSpec := range inputArtifactSpecs {
			if inputArtifactSpec.Type() != artifact.TableType &&
				inputArtifactSpec.Type() != artifact.FloatType &&
				inputArtifactSpec.Type() != artifact.JsonType {
				return "", errors.New("Inputs to metric operator must be Table, Float, or Parameter Artifacts.")
			}
			inputArtifactTypes = append(inputArtifactTypes, inputArtifactSpec.Type())
		}
		outputArtifactTypes := []artifact.Type{artifact.BoolType}

		return ScheduleFunction(
			ctx,
			opSpec.Check().Function,
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

	if opSpec.IsExtract() {
		if len(inputArtifactSpecs) != 0 {
			return "", ErrWrongNumInputs
		}
		if len(outputArtifactSpecs) != 1 {
			return "", ErrWrongNumOutputs
		}
		if len(outputContentPaths) != 1 {
			return "", ErrWrongNumArtifactContentPaths
		}
		if len(outputMetadataPaths) != 1 {
			return "", ErrWrongNumArtifactMetadataPaths
		}

		return ScheduleExtract(
			ctx,
			*opSpec.Extract(),
			metadataPath,
			outputContentPaths[0],
			outputMetadataPaths[0],
			storageConfig,
			jobManager,
			vaultObject,
		)
	}

	if opSpec.IsLoad() {
		if len(inputArtifactSpecs) != 1 {
			return "", ErrWrongNumInputs
		}
		if len(outputArtifactSpecs) != 0 {
			return "", ErrWrongNumOutputs
		}
		if len(inputContentPaths) != 1 {
			return "", ErrWrongNumArtifactContentPaths
		}
		if len(inputMetadataPaths) != 1 {
			return "", ErrWrongNumArtifactMetadataPaths
		}
		return ScheduleLoad(
			ctx,
			*opSpec.Load(),
			metadataPath,
			inputContentPaths[0],
			inputMetadataPaths[0],
			storageConfig,
			jobManager,
			vaultObject,
		)
	}

	if opSpec.IsParam() {
		if len(inputArtifactSpecs) != 0 {
			return "", ErrWrongNumInputs
		}
		if len(outputArtifactSpecs) != 1 {
			return "", ErrWrongNumOutputs
		}
		if !outputArtifactSpecs[0].IsJson() {
			return "", errors.Newf("Internal Error: parameter must output a JSON artifact.")
		}
		if len(outputContentPaths) != 1 {
			return "", ErrWrongNumArtifactContentPaths
		}
		if len(outputMetadataPaths) != 1 {
			return "", ErrWrongNumArtifactMetadataPaths
		}

		return ScheduleParam(
			ctx,
			*opSpec.Param(),
			metadataPath,
			outputContentPaths[0],
			outputMetadataPaths[0],
			storageConfig,
			jobManager,
		)
	}

	if opSpec.IsSystemMetric() {
		fmt.Println("WEEEE WE ARE SYSTEM THE METRICING")
		outputArtifactTypes := []artifact.Type{artifact.FloatType}
		return ScheduleSystemMetric(
			ctx,
			*opSpec.SystemMetric(),
			metadataPath,
			inputContentPaths,
			inputMetadataPaths,
			outputContentPaths,
			outputMetadataPaths,
			outputArtifactTypes,
			storageConfig,
			jobManager,
		)
	}

	// If we reach here, the operator opSpec type is not supported.
	return "", errors.Newf("Unsupported operator opSpec with type %s", opSpec.Type())
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
		fmt.Println("we are the 1 \n\n\n")
		// Operator wrote metadata (including an error) to storage
		fmt.Println("Operator wrote metadata (including an error) to storage \n\n\n")
		return &operatorResultMetadata, shared.FailedExecutionStatus, UserFailure
	}

	if jobStatus == shared.FailedExecutionStatus {
		// Operator wrote metadata (without an error) to storage, but k8s marked the job as failed
		fmt.Println("Operator wrote metadata (without an error) to storage, but k8s marked the job as failed  \n\n\n")
		return &operatorResultMetadata, shared.FailedExecutionStatus, UserFailure
	}

	return &operatorResultMetadata, shared.SucceededExecutionStatus, NoFailure
}
