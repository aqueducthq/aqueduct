package handler

import (
	"context"
	"fmt"
	"net/http"

	"github.com/aqueducthq/aqueduct/cmd/server/routes"
	"github.com/aqueducthq/aqueduct/lib/collections/integration"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	aq_context "github.com/aqueducthq/aqueduct/lib/context"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/aqueducthq/aqueduct/lib/job"
	"github.com/aqueducthq/aqueduct/lib/vault"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector/auth"
	workflow_utils "github.com/aqueducthq/aqueduct/lib/workflow/utils"
	"github.com/dropbox/godropbox/errors"
	"github.com/go-chi/chi"
	"github.com/google/uuid"
)

// Doesn't currently work for S3 because it's too expensive to list.

// Route: /integration/{integrationId}/objects
// Method: GET
// Params:
//	`integrationId`: ID for `integration` object
// Request:
//	Headers:
//		`api-key`: user's API Key
// Response:
//  Body:
//		objects written by workflows at the integration.

// Get objects from the specified integration.
type IntegrationObjectsHandler struct {
	GetHandler

	Database          database.Database
	StorageConfig     *shared.StorageConfig
	JobManager        job.JobManager
	Vault             vault.Vault
	IntegrationReader integration.Reader
}

type IntegrationObjectsArgs struct {
	*aq_context.AqContext
	integrationId uuid.UUID
}

type IntegrationObjectsResponse struct {
	ObjectNames []string `json:"object_names"`
}

func (*IntegrationObjectsHandler) Name() string {
	return "IntegrationObjects"
}

func (h *IntegrationObjectsHandler) Prepare(r *http.Request) (interface{}, int, error) {
	aqContext, statusCode, err := aq_context.ParseAqContext(r.Context())
	if err != nil {
		return nil, statusCode, errors.Wrap(err, "Unable to parse arguments.")
	}

	integrationIdStr := chi.URLParam(r, routes.IntegrationIdUrlParam)
	integrationId, err := uuid.Parse(integrationIdStr)
	if err != nil {
		return nil, http.StatusBadRequest, errors.Wrap(err, "Malformed integration ID.")
	}

	return &IntegrationObjectsArgs{
		AqContext:     aqContext,
		integrationId: integrationId,
	}, http.StatusOK, nil
}

func (h *IntegrationObjectsHandler) Perform(ctx context.Context, interfaceArgs interface{}) (interface{}, int, error) {
	args := interfaceArgs.(*IntegrationObjectsArgs)

	integrationObject, err := h.IntegrationReader.GetIntegration(
		ctx,
		args.integrationId,
		h.Database,
	)
	if err != nil {
		return nil, http.StatusBadRequest, errors.Wrap(err, "Unable to retrieve integration.")
	}

	if _, ok := integration.GetRelationalDatabaseIntegrations()[integrationObject.Service]; !ok {
		return nil, http.StatusBadRequest, errors.New("List objects request is only allowed for relational databases. (Too expensive to list objects for S3)")
	}

	jobMetadataPath := fmt.Sprintf("list-objects-metadata-%s", args.RequestId)
	jobResultPath := fmt.Sprintf("list-objects-result-%s", args.RequestId)

	defer func() {
		// Delete storage files created for list objects job metadata
		go workflow_utils.CleanupStorageFiles(ctx, h.StorageConfig, []string{jobMetadataPath, jobResultPath})
	}()

	config, err := auth.ReadConfigFromSecret(ctx, integrationObject.Id, h.Vault)
	if err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unable to parse integration config.")
	}

	jobName := fmt.Sprintf("integration-objects-%s", uuid.New().String())
	jobSpec := job.NewDiscoverSpec(
		jobName,
		h.StorageConfig,
		jobMetadataPath,
		integrationObject.Service,
		config,
		jobResultPath,
	)

	if err := h.JobManager.Launch(ctx, jobName, jobSpec); err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unable to launch integration objects job.")
	}

	jobStatus, err := job.PollJob(ctx, jobName, h.JobManager, pollDiscoverInterval, pollDiscoverTimeout)
	if err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unexpected error while waiting for integration objects job to finish.")
	}

	if jobStatus == shared.FailedExecutionStatus {
		return nil, http.StatusInternalServerError, errors.New("Unexpected error while listing objects.")
	}

	var metadata shared.ExecutionState
	if err := workflow_utils.ReadFromStorage(
		ctx,
		h.StorageConfig,
		jobMetadataPath,
		&metadata,
	); err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unable to retrieve operator metadata from storage.")
	}

	if metadata.Error != nil {
		return nil, http.StatusBadRequest, errors.Newf("Unable to list objects: %v", metadata.Error.Context)
	}

	var objectNames []string
	if err := workflow_utils.ReadFromStorage(
		ctx,
		h.StorageConfig,
		jobResultPath,
		&objectNames,
	); err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unable to retrieve object names from storage.")
	}

	return IntegrationObjectsResponse{
		ObjectNames: objectNames,
	}, http.StatusOK, nil
}
