package scheduler

import (
	"context"
	"fmt"

	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/job"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/system_metric"
	"github.com/google/uuid"
)

func generateSystemMetricJobName() string {
	return fmt.Sprintf("system_metric-operator-%s", uuid.New().String())
}

func ScheduleSystemMetric(
	ctx context.Context,
	spec system_metric.SystemMetric,
	metadataPath string,
	inputMetadataPaths []string,
	outputContentPath string,
	outputMetadataPath string,
	storageConfig *shared.StorageConfig,
	jobManager job.JobManager,
) (job.Spec, error) {
	jobName := generateSystemMetricJobName()

	jobSpec := job.NewSystemMetricSpec(
		jobName,
		storageConfig,
		metadataPath,
		spec.MetricName,
		inputMetadataPaths,
		outputContentPath,
		outputMetadataPath,
	)

	return jobSpec, nil
}
