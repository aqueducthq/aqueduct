package _000013_add_workflow_dag_engine_config

import (
	"context"

	"github.com/aqueducthq/aqueduct/lib/database"
)

func UpPostgres(ctx context.Context, db database.Database) error {
	return db.Execute(ctx, upPostgresScript)
}

func DownPostgres(ctx context.Context, db database.Database) error {
	return db.Execute(ctx, downPostgresScript)
}

func UpSqlite(ctx context.Context, db database.Database) error {
	// SQLite doesn't easily allow for inserting JSON data as a raw query,
	// so we must split up the column add into 3 steps.

	txn, err := db.BeginTx(ctx)
	if err != nil {
		return err
	}
	defer database.TxnRollbackIgnoreErr(ctx, txn)

	// Step 1: Add the column and allow it to take on NULL values
	addColumnStmt := "ALTER TABLE workflow_dag ADD COLUMN engine_config BLOB;"
	if err := txn.Execute(ctx, addColumnStmt); err != nil {
		return err
	}

	// Step 2: For each row with NULL `engine_config`, set it to the default value
	if err := setDefaultEngineConfig(ctx, txn); err != nil {
		return err
	}

	// Step 3: Change `engine_config` to be NOT NULL
	if err := makeEngineConfigNotNull(ctx, txn); err != nil {
		return err
	}

	return txn.Commit(ctx)
}
