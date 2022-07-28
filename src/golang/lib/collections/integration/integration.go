package integration

import (
	"context"
	"time"

	"github.com/aqueducthq/aqueduct/lib/collections/utils"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/google/uuid"
)

type Integration struct {
	Id             uuid.UUID      `db:"id"`
	UserId         utils.NullUUID `db:"user_id"`
	OrganizationId string         `db:"organization_id"`
	Service        Service        `db:"service"`
	Name           string         `db:"name"`
	Config         utils.Config   `db:"config"`
	CreatedAt      time.Time      `db:"created_at"`
	Validated      bool           `db:"validated"`
}

type Reader interface {
	GetIntegration(
		ctx context.Context,
		id uuid.UUID,
		db database.Database,
	) (*Integration, error)
	GetIntegrations(
		ctx context.Context,
		ids []uuid.UUID,
		db database.Database,
	) ([]Integration, error)
	GetIntegrationsByServiceAndUser(
		ctx context.Context,
		service Service,
		userId uuid.UUID,
		db database.Database,
	) ([]Integration, error)
	GetIntegrationsByOrganization(
		ctx context.Context,
		organizationId string,
		db database.Database,
	) ([]Integration, error)
	GetIntegrationsByUser(
		ctx context.Context,
		organizationId string,
		userId uuid.UUID,
		db database.Database,
	) ([]Integration, error)
	GetIntegrationsByConfigField(
		ctx context.Context,
		fieldName string,
		fieldValue string,
		db database.Database,
	) ([]Integration, error)
	ValidateIntegrationOwnership(
		ctx context.Context,
		integrationId uuid.UUID,
		organizationId string,
		db database.Database,
	) (bool, error)
	GetIntegrationByNameAndUser(
		ctx context.Context,
		integrationName string,
		userId uuid.UUID,
		organizationId string,
		db database.Database,
	) (*Integration, error)
}

type Writer interface {
	CreateIntegration(
		ctx context.Context,
		organizationId string,
		service Service,
		name string,
		config *utils.Config,
		validated bool,
		db database.Database,
	) (*Integration, error)
	CreateIntegrationForUser(
		ctx context.Context,
		organizationId string,
		userId uuid.UUID,
		service Service,
		name string,
		config *utils.Config,
		validated bool,
		db database.Database,
	) (*Integration, error)
	UpdateIntegration(
		ctx context.Context,
		id uuid.UUID,
		changedColumns map[string]interface{},
		db database.Database,
	) (*Integration, error)
	DeleteIntegration(
		ctx context.Context,
		id uuid.UUID,
		db database.Database,
	) error
}

func NewReader(dbConf *database.DatabaseConfig) (Reader, error) {
	if dbConf.Type == database.PostgresType {
		return newPostgresReader(), nil
	}

	if dbConf.Type == database.SqliteType {
		return newSqliteReader(), nil
	}

	return nil, database.ErrUnsupportedDbType
}

func NewWriter(dbConf *database.DatabaseConfig) (Writer, error) {
	if dbConf.Type == database.PostgresType {
		return newPostgresWriter(), nil
	}

	if dbConf.Type == database.SqliteType {
		return newSqliteWriter(), nil
	}

	return nil, database.ErrUnsupportedDbType
}
