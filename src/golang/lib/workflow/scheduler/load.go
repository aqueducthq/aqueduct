package scheduler

import (
	"context"
	"fmt"

	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/job"
	"github.com/aqueducthq/aqueduct/lib/vault"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector/auth"
	"github.com/google/uuid"
)

func generateLoadJobName() string {
	return fmt.Sprintf("load-operator-%s", uuid.New().String())
}

func ScheduleLoad(
	ctx context.Context,
	spec connector.Load,
	metadataPath string,
	inputContentPath string,
	inputMetadataPath string,
	storageConfig *shared.StorageConfig,
	jobManager job.JobManager,
	vaultObject vault.Vault,
) (job.Spec, error) {
	config, err := auth.ReadConfigFromSecret(ctx, spec.IntegrationId, vaultObject)
	if err != nil {
		return nil, err
	}

	jobName := generateLoadJobName()

	jobSpec := job.NewLoadSpec(
		jobName,
		storageConfig,
		metadataPath,
		spec.Service,
		config,
		spec.Parameters,
		inputContentPath,
		inputMetadataPath,
	)

	return jobSpec, nil
}
