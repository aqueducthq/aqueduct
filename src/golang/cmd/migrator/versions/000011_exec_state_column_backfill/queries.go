package _000011_exec_state_column_backfill

import (
	"context"

	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/collections/utils"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/google/uuid"
)

type opResultWithMetadata struct {
	Id       uuid.UUID              `db:"id" json:"id"`
	Status   shared.ExecutionStatus `db:"status" json:"status"`
	Metadata NullMetadata           `db:"metadata" json:"metadata"`
}

type opResultWithExecState struct {
	Id        uuid.UUID                 `db:"id" json:"id"`
	Status    shared.ExecutionStatus    `db:"status" json:"status"`
	ExecState shared.NullExecutionState `db:"exec_state" json:"exec_state"`
}

func getOpResultsWithMetadata(
	ctx context.Context,
	db database.Database,
) ([]opResultWithMetadata, error) {
	query := "SELECT id, status, metadata FROM operator_result;"

	var response []opResultWithMetadata
	err := db.Query(ctx, &response, query)
	return response, err
}

func updateExecState(
	ctx context.Context,
	id uuid.UUID,
	execState *shared.ExecutionState,
	db database.Database,
) error {
	changes := map[string]interface{}{
		"exec_state": execState,
	}
	return utils.UpdateRecord(ctx, changes, "operator_result", "id", id, db)
}

func getOpResultsWithExecState(
	ctx context.Context,
	db database.Database,
) ([]opResultWithExecState, error) {
	query := "SELECT id, status, exec_state FROM operator_result;"

	var response []opResultWithExecState
	err := db.Query(ctx, &response, query)
	return response, err
}

func updateMetadata(
	ctx context.Context,
	id uuid.UUID,
	metadata *Metadata,
	db database.Database,
) error {
	changes := map[string]interface{}{
		"metadata": metadata,
	}
	return utils.UpdateRecord(ctx, changes, "operator_result", "id", id, db)
}
