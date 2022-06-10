package handler

import (
	"context"
	"net/http"

	"github.com/aqueducthq/aqueduct/cmd/server/routes"
	"github.com/aqueducthq/aqueduct/lib/collections/artifact"
	"github.com/aqueducthq/aqueduct/lib/collections/artifact_result"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/collections/workflow_dag"
	aq_context "github.com/aqueducthq/aqueduct/lib/context"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/aqueducthq/aqueduct/lib/storage"
	"github.com/dropbox/godropbox/errors"
	"github.com/go-chi/chi"
	"github.com/google/uuid"
)

// Route: /artifact_result/{workflowDagResultId}/{artifactId}
// Method: GET
// Params:
//	`workflowDagResultId`: ID for `workflow_dag_result` object
//	`artifactId`: ID for `artifact` object
// Request:
//	Headers:
//		`api-key`: user's API Key
// Response:
//	Body:
//		serialized `getArtifactResultResponse`,
//		metadata and content of the result of `artifactId` on the given workflow_dag_result object.
type getArtifactResultArgs struct {
	*aq_context.AqContext
	workflowDagResultId uuid.UUID
	artifactId          uuid.UUID
}

type getArtifactResultResponse struct {
	Status shared.ExecutionStatus `json:"status"`
	Schema []map[string]string    `json:"schema"`
	Data   string                 `json:"data"`
}

type GetArtifactResultHandler struct {
	GetHandler

	Database             database.Database
	ArtifactReader       artifact.Reader
	ArtifactResultReader artifact_result.Reader
	WorkflowDagReader    workflow_dag.Reader
}

func (*GetArtifactResultHandler) Name() string {
	return "GetArtifactResult"
}

func (h *GetArtifactResultHandler) Prepare(r *http.Request) (interface{}, int, error) {
	aqContext, statusCode, err := aq_context.ParseAqContext(r.Context())
	if err != nil {
		return nil, statusCode, err
	}

	workflowDagResultIdStr := chi.URLParam(r, routes.WorkflowDagResultIdUrlParam)
	workflowDagResultId, err := uuid.Parse(workflowDagResultIdStr)
	if err != nil {
		return nil, http.StatusBadRequest, errors.Wrap(err, "Malformed workflow dag result ID.")
	}

	artifactIdStr := chi.URLParam(r, routes.ArtifactIdUrlParam)
	artifactId, err := uuid.Parse(artifactIdStr)
	if err != nil {
		return nil, http.StatusBadRequest, errors.Wrap(err, "Malformed artifact ID.")
	}

	ok, err := h.ArtifactReader.ValidateArtifactOwnership(
		r.Context(),
		aqContext.OrganizationId,
		artifactId,
		h.Database,
	)
	if err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unexpected error during artifact ownership validation.")
	}
	if !ok {
		return nil, http.StatusBadRequest, errors.Wrap(err, "The organization does not own this artifact.")
	}

	return &getArtifactResultArgs{
		AqContext:           aqContext,
		workflowDagResultId: workflowDagResultId,
		artifactId:          artifactId,
	}, http.StatusOK, nil
}

func (h *GetArtifactResultHandler) Perform(ctx context.Context, interfaceArgs interface{}) (interface{}, int, error) {
	args := interfaceArgs.(*getArtifactResultArgs)

	emptyResp := getArtifactResultResponse{}

	workflowDag, err := h.WorkflowDagReader.GetWorkflowDagByWorkflowDagResultId(
		ctx,
		args.workflowDagResultId,
		h.Database,
	)
	if err != nil {
		return emptyResp, http.StatusInternalServerError, errors.Wrap(err, "Unexpected error occurred when retrieving workflow dag.")
	}

	dbArtifactResult, err := h.ArtifactResultReader.GetArtifactResultByWorkflowDagResultIdAndArtifactId(
		ctx,
		args.workflowDagResultId,
		args.artifactId,
		h.Database,
	)
	if err != nil {
		return emptyResp, http.StatusInternalServerError, errors.Wrap(err, "Unexpected error occurred when retrieving artifact result.")
	}

	response := getArtifactResultResponse{
		Status: dbArtifactResult.Status,
	}

	if !dbArtifactResult.Metadata.IsNull {
		response.Schema = dbArtifactResult.Metadata.Schema
	}

	if dbArtifactResult.Status == shared.SucceededExecutionStatus {
		// We retrieve the data only when the artifact result status is `succeeded`.
		data, err := storage.NewStorage(&workflowDag.StorageConfig).Get(
			ctx,
			dbArtifactResult.ContentPath,
		)
		if err != nil {
			return emptyResp, http.StatusInternalServerError, errors.Wrap(err, "Failed to retrieve data for the artifact result.")
		}

		response.Data = string(data)
	}

	return response, http.StatusOK, nil
}
