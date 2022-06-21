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

func generateExtractJobName() string {
	return fmt.Sprintf("extract-operator-%s", uuid.New().String())
}

func ScheduleExtract(
	ctx context.Context,
	spec connector.Extract,
	metadataPath string,
	outputContentPath string,
	outputMetadataPath string,
	storageConfig *shared.StorageConfig,
	jobManager job.JobManager,
	vaultObject vault.Vault,
) (job.Spec, error) {
	config, err := auth.ReadConfigFromSecret(ctx, spec.IntegrationId, vaultObject)
	if err != nil {
		return nil, err
	}

	jobName := generateExtractJobName()

	jobSpec := job.NewExtractSpec(
		jobName,
		storageConfig,
		metadataPath,
		spec.Service,
		config,
		spec.Parameters,
		outputContentPath,
		outputMetadataPath,
	)

	return jobSpec, nil
}
