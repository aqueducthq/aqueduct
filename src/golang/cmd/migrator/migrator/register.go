package migrator

import (
	"context"

	_000001 "github.com/aqueducthq/aqueduct/cmd/migrator/versions/000001_base"
	_000002 "github.com/aqueducthq/aqueduct/cmd/migrator/versions/000002_add_user_id_to_integration"
	_000003 "github.com/aqueducthq/aqueduct/cmd/migrator/versions/000003_add_storage_column"
	_000004 "github.com/aqueducthq/aqueduct/cmd/migrator/versions/000004_storage_interface_backfill"
	_000005 "github.com/aqueducthq/aqueduct/cmd/migrator/versions/000005_storage_interface_not_null"
	_000006 "github.com/aqueducthq/aqueduct/cmd/migrator/versions/000006_add_retention_policy_column"
	_000007 "github.com/aqueducthq/aqueduct/cmd/migrator/versions/000007_workflow_dag_edge_pk"
	_000008 "github.com/aqueducthq/aqueduct/cmd/migrator/versions/000008_delete_s3_config"
	_000009 "github.com/aqueducthq/aqueduct/cmd/migrator/versions/000009_metadata_interface_backfill"
<<<<<<< HEAD
	_000010 "github.com/aqueducthq/aqueduct/cmd/migrator/versions/000010_add_workflow_dag_runtime_config"
=======
	_000010 "github.com/aqueducthq/aqueduct/cmd/migrator/versions/000010_add_workflow_dag_engine_config"
>>>>>>> eng-877-implement-airflow-compile-job
	"github.com/aqueducthq/aqueduct/lib/database"
)

var registeredMigrations = map[int64]*migration{}

type migrationFunc func(context.Context, database.Database) error

type migration struct {
	upPostgres   migrationFunc
	upSqlite     migrationFunc
	downPostgres migrationFunc
	name         string
}

func init() {
	registeredMigrations[1] = &migration{
		upPostgres: _000001.UpPostgres, upSqlite: _000001.UpSqlite,
		name: "base",
	}
	registeredMigrations[2] = &migration{
		upPostgres: _000002.UpPostgres, upSqlite: _000002.UpSqlite,
		downPostgres: _000002.DownPostgres,
		name:         "add integration.user_id",
	}
	registeredMigrations[3] = &migration{
		upPostgres: _000003.UpPostgres, upSqlite: _000003.UpSqlite,
		downPostgres: _000003.DownPostgres,
		name:         "add workflow_dag.storage_config",
	}
	registeredMigrations[4] = &migration{
		upPostgres: _000004.Up, upSqlite: _000004.Up,
		downPostgres: _000004.Down,
		name:         "backfill workflow_dag.storage_config and operator.spec->>storage_path",
	}
	registeredMigrations[5] = &migration{
		upPostgres: _000005.UpPostgres, upSqlite: _000005.UpSqlite,
		downPostgres: _000005.DownPostgres,
		name:         "add not null constraint to workflow_dag.storage_config",
	}
	registeredMigrations[6] = &migration{
		upPostgres: _000006.UpPostgres, upSqlite: _000006.UpSqlite,
		downPostgres: _000006.DownPostgres,
		name:         "add workflow.retention_policy",
	}
	registeredMigrations[7] = &migration{
		upPostgres: _000007.UpPostgres, upSqlite: _000007.UpSqlite,
		downPostgres: _000007.DownPostgres,
		name:         "add primary key constraint to workflow_dag_edge on workflow_dag_id, from_id, to_id",
	}

	registeredMigrations[8] = &migration{
		upPostgres: _000008.UpPostgres, upSqlite: _000008.UpSqlite,
		downPostgres: _000008.DownPostgres,
		name:         "delete outdated s3_config column",
	}

	registeredMigrations[9] = &migration{
		upPostgres: _000009.Up, upSqlite: _000009.Up,
		downPostgres: _000009.Down,
		name:         "backfill metadata in artifact_results",
	}
	registeredMigrations[10] = &migration{
		upPostgres: _000010.UpPostgres, upSqlite: _000010.UpSqlite,
		downPostgres: _000010.DownPostgres,
		name:         "add workflow_dag.engine_config",
	}
}
