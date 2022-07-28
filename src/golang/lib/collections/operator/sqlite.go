package operator

import (
	"context"
	"fmt"

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

func (r *sqliteReaderImpl) GetOperatorsByIntegrationId(
	ctx context.Context,
	integrationId uuid.UUID,
	db database.Database,
) ([]DBOperator, error) {
	getOperatorsByIntegrationIdQuery := fmt.Sprintf(
		`SELECT %s FROM %s
		WHERE json_extract(spec, '$.load.integration_id') = $1
		OR json_extract(spec, '$.extract.integration_id') = $2`,
		allColumns(),
		tableName,
	)

	var operators []DBOperator
	err := db.Query(
		ctx,
		&operators,
		getOperatorsByIntegrationIdQuery,
		integrationId,
		integrationId,
	)
	return operators, err
}

func (w *sqliteWriterImpl) CreateOperator(
	ctx context.Context,
	name string,
	description string,
	spec *Spec,
	db database.Database,
) (*DBOperator, error) {
	insertColumns := []string{IdColumn, NameColumn, DescriptionColumn, SpecColumn}
	insertOperatorStmt := db.PrepareInsertWithReturnAllStmt(tableName, insertColumns, allColumns())

	id, err := utils.GenerateUniqueUUID(ctx, tableName, db)
	if err != nil {
		return nil, err
	}

	args := []interface{}{id, name, description, spec}

	var operator DBOperator
	err = db.Query(ctx, &operator, insertOperatorStmt, args...)
	return &operator, err
}

func (r *sqliteReaderImpl) GetDistinctLoadOperatorsByWorkflowId(
	ctx context.Context,
	workflowId uuid.UUID,
	db database.Database,
) ([]GetDistinctLoadOperatorsByWorkflowIdResponse, error) {
	query := `
	SELECT DISTINCT
			operator.name AS operator_name, 
			integration.name AS integration_name, 
			json_extract(operator.spec, '$.load.integration_id') AS integration_id, 
			json_extract(operator.spec, '$.load.service') AS service, 
			json_extract(operator.spec, '$.load.parameters.table') AS table_name, 
			json_extract(operator.spec, '$.load.parameters.update_mode') AS update_mode
		FROM 
			operator, integration
		WHERE (
			json_extract(spec, '$.type')='load' AND 
			integration.id = json_extract(operator.spec, '$.load.integration_id') AND
			EXISTS (
				SELECT 1 
				FROM 
					workflow_dag_edge, workflow_dag 
				WHERE 
					( 
						workflow_dag_edge.from_id = operator.id OR 
						workflow_dag_edge.to_id = operator.id 
					) AND 
					workflow_dag_edge.workflow_dag_id = workflow_dag.id AND 
					workflow_dag.workflow_id = $1
			)
		);`

	var workflowSpecs []GetDistinctLoadOperatorsByWorkflowIdResponse
	err := db.Query(ctx, &workflowSpecs, query, workflowId)
	return workflowSpecs, err
}
