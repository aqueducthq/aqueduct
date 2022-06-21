package handler

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/aqueducthq/aqueduct/cmd/server/routes"
	"github.com/aqueducthq/aqueduct/lib/collections/integration"
	"github.com/aqueducthq/aqueduct/lib/collections/operator_result"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	aq_context "github.com/aqueducthq/aqueduct/lib/context"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/aqueducthq/aqueduct/lib/job"
	"github.com/aqueducthq/aqueduct/lib/storage"
	"github.com/aqueducthq/aqueduct/lib/vault"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector"
	"github.com/aqueducthq/aqueduct/lib/workflow/scheduler"
	workflow_utils "github.com/aqueducthq/aqueduct/lib/workflow/utils"
	"github.com/dropbox/godropbox/errors"
	"github.com/go-chi/chi"
	"github.com/google/uuid"
)

const (
	PollPreviewTableInterval = 500 * time.Millisecond
	PollPreviewTableTimeout  = 60 * time.Second
)

// Route: /integration/{integrationId}/preview_table
// Method: GET
// Params:
//	`integrationId`: ID of the relational database integration
// Request:
//	Headers:
//		`api-key`: user's API Key
//		`table-name`: name of the table to preview
// Response:
//	Body:
//		serialized `previewTableResponse`, the json serialized table content

type previewTableArgs struct {
	*aq_context.AqContext
	integrationId uuid.UUID
	tableName     string
}

type previewTableResponse struct {
	Data string `json:"data"`
}

type PreviewTableHandler struct {
	GetHandler

	Database          database.Database
	IntegrationReader integration.Reader
	StorageConfig     *shared.StorageConfig
	JobManager        job.JobManager
	Vault             vault.Vault
}

func (*PreviewTableHandler) Name() string {
	return "PreviewTable"
}

func (*PreviewTableHandler) Headers() []string {
	return []string{routes.TableNameHeader}
}

func (h *PreviewTableHandler) Prepare(r *http.Request) (interface{}, int, error) {
	aqContext, statusCode, err := aq_context.ParseAqContext(r.Context())
	if err != nil {
		return nil, statusCode, err
	}

	integrationIdStr := chi.URLParam(r, routes.IntegrationIdUrlParam)
	integrationId, err := uuid.Parse(integrationIdStr)
	if err != nil {
		return nil, http.StatusBadRequest, errors.Wrap(err, "Malformed integration ID.")
	}

	tableName := r.Header.Get(routes.TableNameHeader)
	if tableName == "" {
		return nil, http.StatusBadRequest, errors.Wrap(err, "No table name specified.")
	}

	ok, err := h.IntegrationReader.ValidateIntegrationOwnership(
		r.Context(),
		integrationId,
		aqContext.OrganizationId,
		h.Database,
	)
	if err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unexpected error during integration ownership validation.")
	}
	if !ok {
		return nil, http.StatusBadRequest, errors.Wrap(err, "The organization does not own this integration.")
	}

	return &previewTableArgs{
		AqContext:     aqContext,
		integrationId: integrationId,
		tableName:     tableName,
	}, http.StatusOK, nil
}

func (h *PreviewTableHandler) Perform(ctx context.Context, interfaceArgs interface{}) (interface{}, int, error) {
	args := interfaceArgs.(*previewTableArgs)

	integrationObject, err := h.IntegrationReader.GetIntegration(
		ctx,
		args.integrationId,
		h.Database,
	)
	if err != nil {
		return nil, http.StatusBadRequest, errors.Wrap(err, "Unable to retrieve integration.")
	}

	if _, ok := integration.GetRelationalDatabaseIntegrations()[integrationObject.Service]; !ok {
		return nil, http.StatusBadRequest, errors.Wrap(err, "Preview table request is only allowed for relational databases.")
	}

	operatorMetadataPath := fmt.Sprintf("operator-metadata-%s", args.RequestId)
	artifactMetadataPath := fmt.Sprintf("artifact-metadata-%s", args.RequestId)
	artifactContentPath := fmt.Sprintf("artifact-content-%s", args.RequestId)

	defer func() {
		// Delete storage files created for preview table data
		go workflow_utils.CleanupStorageFiles(ctx, h.StorageConfig, []string{operatorMetadataPath, artifactMetadataPath, artifactContentPath})
	}()

	query := fmt.Sprintf("SELECT * FROM %s;", args.tableName)

	jobSpec, err := scheduler.GenerateExtractJobSpec(
		ctx,
		connector.Extract{
			Service:       integrationObject.Service,
			IntegrationId: integrationObject.Id,
			Parameters: &connector.RelationalDBExtractParams{
				Query: query,
			},
		},
		operatorMetadataPath,
		artifactContentPath,
		artifactMetadataPath,
		h.StorageConfig,
		h.JobManager,
		h.Vault,
	)
	if err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unexpected error while launching job to preview table.")
	}

	if err := h.JobManager.Launch(ctx, jobSpec.Name(), jobSpec); err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unexpected error while launching job to preview table.")
	}

	jobStatus, err := job.PollJob(ctx, jobSpec.Name(), h.JobManager, PollPreviewTableInterval, PollPreviewTableTimeout)
	if err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unexpected error while waiting for the preview table job to finish.")
	}

	if jobStatus == shared.FailedExecutionStatus {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unexpected error while previewing table.")
	}

	var metadata operator_result.Metadata
	if err := workflow_utils.ReadFromStorage(
		ctx,
		h.StorageConfig,
		operatorMetadataPath,
		&metadata,
	); err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unable to retrieve operator metadata from storage.")
	}

	if len(metadata.Error) > 0 {
		return nil, http.StatusBadRequest, errors.Newf("Unable to preview table: %v", metadata.Error)
	}

	data, err := storage.NewStorage(h.StorageConfig).Get(
		ctx,
		artifactContentPath,
	)
	if err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Failed to retrieve data for the table result.")
	}

	return previewTableResponse{
		Data: string(data),
	}, http.StatusOK, nil
}
