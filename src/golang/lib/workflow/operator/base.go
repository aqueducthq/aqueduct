package operator

import (
	"context"
	"fmt"

	"github.com/aqueducthq/aqueduct/lib/collections/operator"
	"github.com/aqueducthq/aqueduct/lib/collections/operator/function"
	"github.com/aqueducthq/aqueduct/lib/collections/operator_result"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/aqueducthq/aqueduct/lib/job"
	"github.com/aqueducthq/aqueduct/lib/vault"
	"github.com/aqueducthq/aqueduct/lib/workflow/artifact"
	"github.com/aqueducthq/aqueduct/lib/workflow/utils"
	"github.com/dropbox/godropbox/errors"
	"github.com/google/uuid"
	log "github.com/sirupsen/logrus"
)

type baseOperator struct {
	dbOperator *operator.DBOperator

	// These fields are set to nil in the preview case.
	resultWriter operator_result.Writer
	resultID     uuid.UUID

	metadataPath string
	jobName      string

	inputs              []artifact.Artifact
	outputs             []artifact.Artifact
	inputContentPaths   []string
	inputMetadataPaths  []string
	outputContentPaths  []string
	outputMetadataPaths []string

	jobManager    job.JobManager
	vaultObject   vault.Vault
	storageConfig *shared.StorageConfig
	db            database.Database

	resultsPersisted bool
}

func (bo *baseOperator) Type() operator.Type {
	return bo.dbOperator.Spec.Type()
}

func (bo *baseOperator) Name() string {
	return bo.dbOperator.Name
}

func (bo *baseOperator) ID() uuid.UUID {
	return bo.dbOperator.Id
}

// A catch-all for execution states that are the system's fault.
// Logs an internal message so that we can debug.
func unknownSystemFailureExecState(err error, logMsg string) *shared.ExecutionState {
	log.Errorf("Execution had system failure: %s. %v", logMsg, err)

	failureType := shared.SystemFailure
	return &shared.ExecutionState{
		Status:      shared.FailedExecutionStatus,
		FailureType: &failureType,
		Error: &shared.Error{
			Context: fmt.Sprintf("%v", err),
			Tip:     shared.TipUnknownInternalError,
		},
	}
}

// fetchExecState assumes that the operator has been computed already.
func (bo *baseOperator) fetchExecState(ctx context.Context) *shared.ExecutionState {
	var execState shared.ExecutionState
	err := utils.ReadFromStorage(
		ctx,
		bo.storageConfig,
		bo.metadataPath,
		&execState,
	)
	if err != nil {
		// Treat this as a system internal error since operator metadata was not found
		return unknownSystemFailureExecState(
			err,
			"Unable to read operator metadata from storage. Operator may have failed before writing metadata.",
		)
	}
	return &execState
}

// GetExecState takes a more wholelistic view of the operator's status than the job manager does,
// and can be called at any time. Because of this, the logic for figuring out the correct state is
// a little more involved.
func (bo *baseOperator) GetExecState(ctx context.Context) (*shared.ExecutionState, error) {
	if bo.jobName == "" {
		return nil, errors.Newf("Internal error: a job name was not set for this operator.")
	}

	status, err := bo.jobManager.Poll(ctx, bo.jobName)
	if err != nil {
		// If the job does not exist, this could mean that is hasn't been run yet (pending),
		// or that it has run already at sometime in the past, but has been garbage collected
		// (succeeded/failed).
		if err == job.ErrJobNotExist {
			// Check whether the operator actually ran.
			if utils.ObjectExistsInStorage(ctx, bo.storageConfig, bo.metadataPath) {
				return bo.fetchExecState(ctx), nil
			}

			// Otherwise, this job has not run yet and is in a pending state.
			return &shared.ExecutionState{
				Status: shared.PendingExecutionStatus,
			}, nil
		} else {
			// This is just an internal polling error state.
			return unknownSystemFailureExecState(err, "Unable to poll job manager."), nil
		}
	} else {
		// The job just completed, so we know we can fetch the results (succeeded/failed).
		if status == shared.FailedExecutionStatus || status == shared.SucceededExecutionStatus {
			return bo.fetchExecState(ctx), nil
		}

		// The job must exist at this point, but it hasn't completed (running).
		return &shared.ExecutionState{
			Status: shared.RunningExecutionStatus,
		}, nil
	}
}

func updateOperatorResultAfterComputation(
	ctx context.Context,
	status shared.ExecutionStatus,
	storageConfig *shared.StorageConfig,
	opMetadataPath string,
	opResultWriter operator_result.Writer,
	opResultID uuid.UUID,
	db database.Database,
) {
	var execState shared.ExecutionState
	err := utils.ReadFromStorage(
		ctx,
		storageConfig,
		opMetadataPath,
		&execState,
	)
	if err != nil {
		log.Errorf(
			"Unable to read operator metadata from storage. Operator may have failed before writing metadata. %v",
			err,
		)
	}

	changes := map[string]interface{}{
		operator_result.StatusColumn:    status,
		operator_result.ExecStateColumn: &execState,
	}

	_, err = opResultWriter.UpdateOperatorResult(
		ctx,
		opResultID,
		changes,
		db,
	)
	if err != nil {
		log.WithFields(
			log.Fields{
				"changes": changes,
			},
		).Errorf("Unable to update operator result metadata: %v", err)
	}
}

func (bo *baseOperator) InitializeResult(ctx context.Context, dagResultID uuid.UUID) error {
	if bo.resultWriter == nil {
		return errors.New("Operator's result writer cannot be nil.")
	}

	operatorResult, err := bo.resultWriter.CreateOperatorResult(
		ctx,
		dagResultID,
		bo.ID(),
		bo.db,
	)
	if err != nil {
		return errors.Wrap(err, "Failed to create operator result record.")
	}
	bo.resultID = operatorResult.Id
	return nil
}

func (bo *baseOperator) PersistResult(ctx context.Context) error {
	if bo.resultsPersisted {
		return errors.Newf("Operator %s was already persisted!", bo.Name())
	}

	execState, err := bo.GetExecState(ctx)
	if err != nil {
		return err
	}
	if execState.Status != shared.FailedExecutionStatus && execState.Status != shared.SucceededExecutionStatus {
		return errors.Newf(fmt.Sprintf("Operator %s has neither succeeded or failed, so it does not have results that can be persisted.", bo.Name()))
	}

	// Best effort writes after this point.
	updateOperatorResultAfterComputation(
		ctx,
		execState.Status,
		bo.storageConfig,
		bo.metadataPath,
		bo.resultWriter,
		bo.resultID,
		bo.db,
	)

	for _, outputArtifact := range bo.outputs {
		err = outputArtifact.PersistResult(ctx, execState.Status)
		if err != nil {
			log.Errorf("Error occurred when persisting artifact %s.", outputArtifact.Name())
		}
	}
	bo.resultsPersisted = true
	return nil
}

func (bo *baseOperator) Finish(ctx context.Context) {
	utils.CleanupStorageFile(ctx, bo.storageConfig, bo.metadataPath)

	for _, outputArtifact := range bo.outputs {
		outputArtifact.Finish(ctx)
	}
}

// Any operator that runs a python function serialized from storage should use this instead of baseOperator.
type baseFunctionOperator struct {
	baseOperator
}

func (bfo *baseFunctionOperator) Finish(ctx context.Context) {
	// If the operator was not persisted to the DB, cleanup the serialized function.
	if !bfo.resultsPersisted {
		utils.CleanupStorageFile(ctx, bfo.storageConfig, bfo.dbOperator.Spec.Function().StoragePath)
	}

	bfo.baseOperator.Finish(ctx)
}

const (
	defaultFunctionEntryPointFile   = "model.py"
	defaultFunctionEntryPointClass  = "Function"
	defaultFunctionEntryPointMethod = "predict"
)

func (bfo *baseFunctionOperator) jobSpec(fn *function.Function) job.Spec {
	entryPoint := fn.EntryPoint
	if entryPoint == nil {
		entryPoint = &function.EntryPoint{
			File:      defaultFunctionEntryPointFile,
			ClassName: defaultFunctionEntryPointClass,
			Method:    defaultFunctionEntryPointMethod,
		}
	}

	return &job.FunctionSpec{
		BasePythonSpec: job.NewBasePythonSpec(
			job.FunctionJobType,
			bfo.jobName,
			*bfo.storageConfig,
			bfo.metadataPath,
		),
		FunctionPath: fn.StoragePath,
		/* `FunctionExtractPath` is set by the job manager at launch time. */
		EntryPointFile:      entryPoint.File,
		EntryPointClass:     entryPoint.ClassName,
		EntryPointMethod:    entryPoint.Method,
		CustomArgs:          fn.CustomArgs,
		InputContentPaths:   bfo.inputContentPaths,
		InputMetadataPaths:  bfo.inputMetadataPaths,
		OutputContentPaths:  bfo.outputContentPaths,
		OutputMetadataPaths: bfo.outputMetadataPaths,
	}
}
