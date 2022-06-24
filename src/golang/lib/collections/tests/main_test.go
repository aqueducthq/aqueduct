package tests

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"testing"
	"time"

	"github.com/aqueducthq/aqueduct/cmd/migrator/migrator"
	"github.com/aqueducthq/aqueduct/lib/database"
	log "github.com/sirupsen/logrus"
)

const (
	schemaVersion = 10

	// Postgres config
	postgresHost     = "localhost"
	postgresPort     = "5432"
	postgresUsername = "postgres"
	postgresPassword = "postgres"
	postgresDatabase = "aqueduct"
)

var (
	runTests = flag.Bool("database-integration", false, "If this flag is set, the database integration tests will be run.")
	dbType   = flag.String("database-type", "sqlite", "Set the database to test against. Options are: postgres or sqlite.")
)

func TestMain(m *testing.M) {
	flag.Parse()

	if !*runTests {
		log.Info("Skipping database integration tests.")
		os.Exit(0)
	}

	cleanup := setup()

	code := m.Run()

	db.Close()
	cleanup()

	os.Exit(code)
}

func setup() func() {
	databaseType := database.Type(*dbType)
	switch databaseType {
	case database.PostgresType:
		return setupPostgres()
	case database.SqliteType:
		return setupSqlite()
	default:
		log.Fatalf("Unknown database type: %v", databaseType)
	}

	return nil
}

func setupSqlite() func() {
	sdb, err := database.NewSqliteInMemoryDatabase(&database.SqliteConfig{})
	if err != nil {
		log.Fatalf("Unable to create Sqlite client: %v", err)
	}

	db = sdb

	initDatabaseSchema(db)
	readers, err = createReaders(db.Config())
	if err != nil {
		log.Fatalf("Unable to create readers: %s", err)
	}

	writers, err = createWriters(db.Config())
	if err != nil {
		log.Fatalf("Unable to create writers: %s", err)
	}

	return func() {}
}

func setupPostgres() func() {
	startPostgres()

	pdb, err := database.NewPostgresDatabaseWithPort(
		&database.PostgresConfig{
			Address:  postgresHost,
			UserName: postgresUsername,
			Password: postgresPassword,
			Database: postgresDatabase,
			Port:     postgresPort,
		},
	)
	if err != nil {
		log.Fatalf("Unable to create Postgres client: %v", err)
	}

	db = pdb

	initDatabaseSchema(db)

	readers, err = createReaders(db.Config())
	if err != nil {
		log.Fatalf("Unable to create readers: %s", err)
	}

	writers, err = createWriters(db.Config())
	if err != nil {
		log.Fatalf("Unable to create writers: %s", err)
	}

	return stopPostgres
}

func startPostgres() {
	cmd := exec.Command(
		"docker",
		"run",
		"-p",
		"5432:5432",
		"--name",
		"db-test",
		"-e",
		fmt.Sprintf("POSTGRES_PASSWORD=%s", postgresPassword),
		"-e",
		fmt.Sprintf("POSTGRES_DB=%s", postgresDatabase),
		"-d",
		"postgres",
	)
	if err := cmd.Run(); err != nil {
		log.Fatalf("Unable to start Postgres Docker container: %v", err)
	}

	log.Infof("Waiting 5s for Postgres container to start...")
	time.Sleep(time.Second * 5)
}

func stopPostgres() {
	cmd := exec.Command(
		"docker",
		"rm",
		"-f",
		"db-test",
	)
	if err := cmd.Run(); err != nil {
		log.Errorf("Unable to stop Postgres Docker container: %v", err)
	}
}

func initDatabaseSchema(db database.Database) {
	cwd, err := os.Getwd()
	if err != nil {
		log.Fatalf("Unable to read cwd: %v", err)
	}

	defer func() {
		err = os.Chdir(cwd)
		if err != nil {
			log.Errorf("Error when changing cwd: %v", err)
		}
	}()

	// The schema change logic must be invoked from the `golang/` directory
	if err := os.Chdir("../../.."); err != nil {
		db.Close()
		log.Fatalf("Unable to change cwd: %v", err)
	}

	if err := migrator.GoTo(context.Background(), schemaVersion, db); err != nil {
		db.Close()
		log.Fatalf("Unable to initialize schema: %v", err)
	}
}
