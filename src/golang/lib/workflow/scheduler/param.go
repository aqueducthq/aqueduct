package scheduler

import (
	"context"
	"fmt"

	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/job"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/param"
	"github.com/google/uuid"
)

func generateParamJobName() string {
	return fmt.Sprintf("param-operator-%s", uuid.New().String())
}

func GenerateParamJobSpec(
	ctx context.Context,
	spec param.Param,
	metadataPath string,
	outputContentPath string,
	outputMetadataPath string,
	storageConfig *shared.StorageConfig,
	jobManager job.JobManager,
) job.Spec {
	jobName := generateParamJobName()

	return job.NewParamSpec(
		jobName,
		storageConfig,
		metadataPath,
		spec.Val,
		outputContentPath,
		outputMetadataPath,
	)
}
