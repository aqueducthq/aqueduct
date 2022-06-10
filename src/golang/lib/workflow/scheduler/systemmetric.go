package scheduler

import (
	"context"
	"fmt"

	"github.com/aqueducthq/aqueduct/lib/collections/artifact"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/job"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/systemmetric"
	"github.com/dropbox/godropbox/errors"
	"github.com/google/uuid"
)

func generateSystemMetricJobName() string {
	return fmt.Sprintf("systemmetric-operator-%s", uuid.New().String())
}

func ScheduleSystemMetric(
	ctx context.Context,
	spec systemmetric.SystemMetric,
	metadataPath string,
	inputContentPaths []string,
	inputMetadataPaths []string,
	outputContentPaths []string,
	outputMetadataPaths []string,
	outputArtifactTypes []artifact.Type,
	storageConfig *shared.StorageConfig,
	jobManager job.JobManager,
) (string, error) {
	jobName := generateSystemMetricJobName()

	jobSpec := job.NewSystemMetricSpec(
		jobName,
		storageConfig,
		metadataPath,
		spec.MetricName,
		inputContentPaths,
		inputMetadataPaths,
		outputContentPaths,
		outputMetadataPaths,
		outputArtifactTypes,
	)
	err := jobManager.Launch(ctx, jobName, jobSpec)
	if err != nil {
		return "", errors.Wrap(err, "Unable to schedule function.")
	}

	return jobName, nil
}
