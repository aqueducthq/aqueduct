package integration

import (
	"context"
	"fmt"
	"time"

	"github.com/aqueducthq/aqueduct/lib/collections/utils"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/aqueducthq/aqueduct/lib/database/stmt_preparers"
	"github.com/dropbox/godropbox/errors"
	"github.com/google/uuid"
)

type standardReaderImpl struct{}

type standardWriterImpl struct{}

func (w *standardWriterImpl) CreateIntegration(
	ctx context.Context,
	organizationId string,
	service Service,
	name string,
	config *utils.Config,
	validated bool,
	db database.Database,
) (*Integration, error) {
	insertColumns := []string{
		OrganizationIdColumn, ServiceColumn, NameColumn, ConfigColumn, CreatedAtColumn, ValidatedColumn,
	}
	insertIntegrationStmt := db.PrepareInsertWithReturnAllStmt(tableName, insertColumns, allColumns())

	args := []interface{}{
		organizationId, service, name, config, time.Now(), validated,
	}

	var integration Integration
	err := db.Query(ctx, &integration, insertIntegrationStmt, args...)
	return &integration, err
}

func (w *standardWriterImpl) CreateIntegrationForUser(
	ctx context.Context,
	organizationId string,
	userId uuid.UUID,
	service Service,
	name string,
	config *utils.Config,
	validated bool,
	db database.Database,
) (*Integration, error) {
	insertColumns := []string{
		OrganizationIdColumn, UserIdColumn, ServiceColumn, NameColumn,
		ConfigColumn, CreatedAtColumn, ValidatedColumn,
	}
	insertIntegrationStmt := db.PrepareInsertWithReturnAllStmt(tableName, insertColumns, allColumns())

	args := []interface{}{
		organizationId, userId, service, name, config, time.Now(), validated,
	}

	var integration Integration
	err := db.Query(ctx, &integration, insertIntegrationStmt, args...)
	return &integration, err
}

func (r *standardReaderImpl) GetIntegration(
	ctx context.Context,
	id uuid.UUID,
	db database.Database,
) (*Integration, error) {
	integrations, err := r.GetIntegrations(ctx, []uuid.UUID{id}, db)
	if err != nil {
		return nil, err
	}

	if len(integrations) != 1 {
		return nil, errors.Newf("Wrong number of integrations fetched")
	}

	return &integrations[0], err
}

func (r *standardReaderImpl) GetIntegrations(
	ctx context.Context,
	ids []uuid.UUID,
	db database.Database,
) ([]Integration, error) {
	if len(ids) == 0 {
		return []Integration{}, nil
	}

	getIntegrationsQuery := fmt.Sprintf(
		"SELECT %s FROM integration WHERE id IN (%s);",
		allColumns(),
		stmt_preparers.GenerateArgsList(len(ids), 1),
	)
	var integrations []Integration
	args := stmt_preparers.CastIdsListToInterfaceList(ids)
	err := db.Query(ctx, &integrations, getIntegrationsQuery, args...)
	return integrations, err
}

func (r *standardReaderImpl) GetIntegrationsByOrganization(
	ctx context.Context,
	organizationId string,
	db database.Database,
) ([]Integration, error) {
	getIntegrationsQuery := fmt.Sprintf(
		"SELECT %s FROM integration WHERE organization_id = $1 AND user_id IS NULL;",
		allColumns(),
	)
	var integrations []Integration

	err := db.Query(ctx, &integrations, getIntegrationsQuery, organizationId)
	return integrations, err
}

func (r *standardReaderImpl) GetIntegrationsByUser(
	ctx context.Context,
	organizationId string,
	userId uuid.UUID,
	db database.Database,
) ([]Integration, error) {
	getIntegrationsQuery := fmt.Sprintf(
		"SELECT %s FROM integration WHERE organization_id = $1 AND (user_id IS NULL OR user_id = $2);",
		allColumns(),
	)
	var integrations []Integration

	err := db.Query(ctx, &integrations, getIntegrationsQuery, organizationId, userId)
	return integrations, err
}

func (r *standardReaderImpl) GetIntegrationByNameAndUser(
	ctx context.Context,
	integrationName string,
	userId uuid.UUID,
	organizationId string,
	db database.Database,
) (*Integration, error) {
	getIntegrationsQuery := fmt.Sprintf(
		"SELECT %s FROM integration WHERE name=$1 AND organization_id = $2 AND (user_id IS NULL OR user_id = $3);",
		allColumns(),
	)
	var integrations []Integration

	err := db.Query(ctx, &integrations, getIntegrationsQuery, integrationName, organizationId, userId)

	if len(integrations) != 1 {
		return nil, errors.Newf("Wrong number of integrations fetched")
	}

	return &integrations[0], err
}

func (r *standardReaderImpl) GetIntegrationsByServiceAndUser(
	ctx context.Context,
	service Service,
	userId uuid.UUID,
	db database.Database,
) ([]Integration, error) {
	getIntegrationsQuery := fmt.Sprintf(
		"SELECT %s FROM integration WHERE service = $1 AND user_id = $2;",
		allColumns(),
	)
	var integrations []Integration

	err := db.Query(ctx, &integrations, getIntegrationsQuery, service, userId)
	return integrations, err
}

func (w *standardWriterImpl) UpdateIntegration(
	ctx context.Context,
	id uuid.UUID,
	changedColumns map[string]interface{},
	db database.Database,
) (*Integration, error) {
	var integration Integration
	err := utils.UpdateRecordToDest(ctx, &integration, changedColumns, tableName, IdColumn, id, allColumns(), db)
	return &integration, err
}

func (w *standardWriterImpl) DeleteIntegration(
	ctx context.Context,
	id uuid.UUID,
	db database.Database,
) error {
	deleteIntegrationStmt := `DELETE FROM integration WHERE id = $1;`
	return db.Execute(ctx, deleteIntegrationStmt, id)
}

func (r *standardReaderImpl) ValidateIntegrationOwnership(
	ctx context.Context,
	integrationId uuid.UUID,
	organizationId string,
	db database.Database,
) (bool, error) {
	query := `SELECT COUNT(*) AS count FROM integration WHERE id = $1 AND organization_id = $2;`
	var count utils.CountResult

	err := db.Query(ctx, &count, query, integrationId, organizationId)
	if err != nil {
		return false, err
	}

	return count.Count == 1, nil
}
