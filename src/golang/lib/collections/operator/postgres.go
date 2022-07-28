package operator

import (
	"context"
	"fmt"

	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/google/uuid"
)

type postgresReaderImpl struct {
	standardReaderImpl
}

type postgresWriterImpl struct {
	standardWriterImpl
}

func newPostgresReader() Reader {
	return &postgresReaderImpl{standardReaderImpl{}}
}

func newPostgresWriter() Writer {
	return &postgresWriterImpl{standardWriterImpl{}}
}

func (r *postgresReaderImpl) GetOperatorsByIntegrationId(
	ctx context.Context,
	integrationId uuid.UUID,
	db database.Database,
) ([]DBOperator, error) {
	getOperatorsByIntegrationIdQuery := fmt.Sprintf(
		`SELECT %s FROM %s
		WHERE json_extract_text(spec, 'load', 'integration_id') = $1
		OR json_extract_text(spec, 'extract', 'integration_id') = $2`,
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

func (r *postgresReaderImpl) GetDistinctLoadOperatorsByWorkflowId(
	ctx context.Context,
	workflowId uuid.UUID,
	db database.Database,
) ([]GetDistinctLoadOperatorsByWorkflowIdResponse, error) {
	query := `
	SELECT DISTINCT 
		operator.name AS operator_name, 
		integration.name AS integration_name, 
		json_extract_path_text(operator.spec, 'load', 'integration_id') AS integration_id,
		json_extract_path_text(operator.spec, 'load', 'service') AS service, 
		json_extract_path_text(operator.spec, 'load', 'parameters', 'table') AS table_name, 
		json_extract_path_text(operator.spec, 'load', 'parameters', 'update_mode')  AS update_mode
	FROM operator, integration 
	WHERE (
		json_extract_path_text(spec, 'type') = 'load' AND 
		integration.id = json_extract_path_text(operator.spec, 'load', 'integration_id') AND
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
