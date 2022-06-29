package workflow_dag

import (
	"context"
	"time"

	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/collections/utils"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/google/uuid"
)

type sqliteReaderImpl struct {
	standardReaderImpl
}

type sqliteWriterImpl struct {
	standardWriterImpl
}

func newSqliteReader() Reader {
	return &sqliteReaderImpl{standardReaderImpl{}}
}

func newSqliteWriter() Writer {
	return &sqliteWriterImpl{standardWriterImpl{}}
}

func (w *sqliteWriterImpl) CreateWorkflowDag(
	ctx context.Context,
	workflowId uuid.UUID,
	storageConfig *shared.StorageConfig,
	runtimeConfig *shared.EngineConfig,
	db database.Database,
) (*WorkflowDag, error) {
	insertColumns := []string{IdColumn, WorkflowIdColumn, CreatedAtColumn, StorageConfigColumn, RuntimeConfigColumn}
	insertWorkflowDagStmt := db.PrepareInsertWithReturnAllStmt(tableName, insertColumns, allColumns())

	id, err := utils.GenerateUniqueUUID(ctx, tableName, db)
	if err != nil {
		return nil, err
	}

	args := []interface{}{id, workflowId, time.Now(), storageConfig, runtimeConfig}

	var workflowDag WorkflowDag
	err = db.Query(ctx, &workflowDag, insertWorkflowDagStmt, args...)
	return &workflowDag, err
}
