package connector

import (
	gh_types "github.com/aqueducthq/aqueduct/lib/collections/operator/connector/github"
)

type ExtractParams interface {
	isExtractParams()
}

type RelationalDBExtractParams struct {
	GithubMetadata *gh_types.GithubMetadata `json:"github_metadata"`
	Query          string                   `json:"query"`
}

type PostgresExtractParams struct{ RelationalDBExtractParams }

type SnowflakeExtractParams struct{ RelationalDBExtractParams }

type MySqlExtractParams struct{ RelationalDBExtractParams }

type RedshiftExtractParams struct{ RelationalDBExtractParams }

type MariaDbExtractParams struct{ RelationalDBExtractParams }

type SqlServerExtractParams struct{ RelationalDBExtractParams }

type BigQueryExtractParams struct{ RelationalDBExtractParams }

type SqliteExtractParams struct{ RelationalDBExtractParams }

type GoogleSheetsExtractParams struct {
	SpreadsheetId string `json:"spreadsheet_id"`
}

type SalesforceExtractParams struct {
	Type  string `json:"type"`
	Query string `json:"query"`
}

type S3ExtractParams struct {
	Filepath     string `json:"filepath"`
	ArtifactType string `json:"artifact_type"`
	Format       string `json:"format,omitempty"`
	Merge        bool   `json:"merge,omitempty"`
}

func (*PostgresExtractParams) isExtractParams() {}

func (*SnowflakeExtractParams) isExtractParams() {}

func (*MySqlExtractParams) isExtractParams() {}

func (*RedshiftExtractParams) isExtractParams() {}

func (*MariaDbExtractParams) isExtractParams() {}

func (*SqlServerExtractParams) isExtractParams() {}

func (*BigQueryExtractParams) isExtractParams() {}

func (*SqliteExtractParams) isExtractParams() {}

func (*GoogleSheetsExtractParams) isExtractParams() {}

func (*RelationalDBExtractParams) isExtractParams() {}

func (*SalesforceExtractParams) isExtractParams() {}

func (*S3ExtractParams) isExtractParams() {}

// `CastToRelationalDBExtractParams` performs a 'casting' from params to `*RelationalDBExtractParams`.
// This is useful for cases where we need to explicitly access relational DB information for extract.
func CastToRelationalDBExtractParams(params ExtractParams) (*RelationalDBExtractParams, bool) {
	postgres, ok := params.(*PostgresExtractParams)
	if ok {
		return &postgres.RelationalDBExtractParams, true
	}

	snowflake, ok := params.(*SnowflakeExtractParams)
	if ok {
		return &snowflake.RelationalDBExtractParams, true
	}

	mysql, ok := params.(*MySqlExtractParams)
	if ok {
		return &mysql.RelationalDBExtractParams, true
	}

	redshift, ok := params.(*RedshiftExtractParams)
	if ok {
		return &redshift.RelationalDBExtractParams, true
	}

	mariadb, ok := params.(*MariaDbExtractParams)
	if ok {
		return &mariadb.RelationalDBExtractParams, true
	}

	sqlserver, ok := params.(*SqlServerExtractParams)
	if ok {
		return &sqlserver.RelationalDBExtractParams, true
	}

	bigquery, ok := params.(*BigQueryExtractParams)
	if ok {
		return &bigquery.RelationalDBExtractParams, true
	}

	sqlite, ok := params.(*SqliteExtractParams)
	if ok {
		return &sqlite.RelationalDBExtractParams, true
	}

	return nil, false
}
