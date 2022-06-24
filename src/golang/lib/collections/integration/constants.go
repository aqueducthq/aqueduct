package integration

import (
	"strings"

	"github.com/dropbox/godropbox/errors"
)

const (
	tableName = "integration"

	// Integration table column names
	IdColumn             = "id"
	OrganizationIdColumn = "organization_id"
	UserIdColumn         = "user_id"
	ServiceColumn        = "service"
	NameColumn           = "name"
	ConfigColumn         = "config"
	CreatedAtColumn      = "created_at"
	ValidatedColumn      = "validated"
)

// Returns a joined string of all Integration columns.
func allColumns() string {
	return strings.Join(
		[]string{
			IdColumn,
			OrganizationIdColumn,
			UserIdColumn,
			ServiceColumn,
			NameColumn,
			ConfigColumn,
			CreatedAtColumn,
			ValidatedColumn,
		},
		",",
	)
}

// Service specifies the name of the integration.
type Service string

// Supported integrations
const (
	Postgres     Service = "Postgres"
	Snowflake    Service = "Snowflake"
	MySql        Service = "MySQL"
	Redshift     Service = "Redshift"
	MariaDb      Service = "MariaDB"
	SqlServer    Service = "SQL Server"
	BigQuery     Service = "BigQuery"
	GoogleSheets Service = "Google Sheets"
	Salesforce   Service = "Salesforce"
	S3           Service = "S3"
	AqueductDemo Service = "Aqueduct Demo"
	Github       Service = "Github"
	Sqlite       Service = "SQLite"
	Airflow      Service = "Airflow"

	DemoDbIntegrationName = "aqueduct_demo"
)

// ParseService decodes s into a Service or an error.
func ParseService(s string) (Service, error) {
	svc := Service(s)
	switch svc {
	case Postgres, Snowflake, MySql, Redshift, MariaDb, SqlServer, BigQuery, GoogleSheets, Salesforce, S3, AqueductDemo, Github, Sqlite:
		return svc, nil
	default:
		return "", errors.Newf("Unknown service: %s", s)
	}
}

func GetRelationalDatabaseIntegrations() map[Service]bool {
	return map[Service]bool{
		Postgres:     true,
		Snowflake:    true,
		MySql:        true,
		Redshift:     true,
		MariaDb:      true,
		SqlServer:    true,
		BigQuery:     true,
		AqueductDemo: true,
		Sqlite:       true,
	}
}
