package handler

import (
	"context"
	"net/http"

	"github.com/aqueducthq/aqueduct/cmd/server/queries"
	"github.com/aqueducthq/aqueduct/lib/collections/operator_result"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	aq_context "github.com/aqueducthq/aqueduct/lib/context"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector"
	"github.com/dropbox/godropbox/errors"
	"github.com/google/uuid"
)

// Route: /artifact_versions
// Method: GET
// Params: None
// Request:
//	Headers:
//		`api-key`: user's API Key
// Response:
//	Body:
//		serialized `getArtifactVersionsResponse`

type getArtifactVersionsResponse struct {
	LatestVersions     map[uuid.UUID]artifactVersions `json:"latest_versions"`
	HistoricalVersions map[uuid.UUID]artifactVersions `json:"historical_versions"`
}

type artifactVersions struct {
	WorkflowName string                        `json:"workflow_name"`
	ArtifactName string                        `json:"artifact_name"`
	WorkflowId   uuid.UUID                     `json:"workflow_id"`
	LoadSpecs    []connector.Load              `json:"load_specs"`
	Versions     map[uuid.UUID]artifactVersion `json:"versions"`
}

type artifactVersion struct {
	Timestamp int64                  `json:"timestamp"`
	Status    shared.ExecutionStatus `json:"status"`
	Error     string                 `json:"error"`
	Checks    []CheckResult          `json:"checks"`
}

type CheckResult struct {
	Name     string                   `json:"name"`
	Status   shared.ExecutionStatus   `json:"status"`
	Metadata operator_result.Metadata `json:"metadata"`
}

type GetArtifactVersionsHandler struct {
	GetHandler

	Database     database.Database
	CustomReader queries.Reader
}

func (*GetArtifactVersionsHandler) Name() string {
	return "GetArtifactVersions"
}

func (*GetArtifactVersionsHandler) Prepare(r *http.Request) (interface{}, int, error) {
	aqContext, statusCode, err := aq_context.ParseAqContext(r.Context())
	if err != nil {
		return nil, statusCode, err
	}

	return aqContext, http.StatusOK, nil
}

func (h *GetArtifactVersionsHandler) Perform(ctx context.Context, interfaceArgs interface{}) (interface{}, int, error) {
	args := interfaceArgs.(*aq_context.AqContext)

	emptyResponse := getArtifactVersionsResponse{}

	latestVersions := make(map[uuid.UUID]artifactVersions)
	historicalVersions := make(map[uuid.UUID]artifactVersions)

	loadOperatorMetadata, err := h.CustomReader.GetLoadOperatorSpecByOrganization(
		ctx,
		args.OrganizationId,
		h.Database,
	)
	if err != nil {
		return emptyResponse, http.StatusInternalServerError, errors.Wrap(err, "Unable to get artifact versions.")
	}

	latestWorkflowDagIdObjects, err := h.CustomReader.GetLatestWorkflowDagIdsByOrganizationId(
		ctx,
		args.OrganizationId,
		h.Database,
	)
	if err != nil {
		return emptyResponse, http.StatusInternalServerError, errors.Wrap(err, "Unable to get artifact versions.")
	}

	loadOperatorIds := make([]uuid.UUID, 0, len(loadOperatorMetadata))
	latestWorkflowDagIds := make([]uuid.UUID, 0, len(latestWorkflowDagIdObjects))

	for _, loadOperator := range loadOperatorMetadata {
		loadOperatorIds = append(loadOperatorIds, loadOperator.LoadOperatorId)
	}

	for _, IdObject := range latestWorkflowDagIdObjects {
		latestWorkflowDagIds = append(latestWorkflowDagIds, IdObject.Id)
	}
	// Handle the no data case so it doesn't throw an error in GetArtifactIdsFromWorkflowDagIdsAndDownstreamOperatorIds
	if len(latestWorkflowDagIds) == 0 || len(loadOperatorIds) == 0 {
		return getArtifactVersionsResponse{
			LatestVersions:     latestVersions,
			HistoricalVersions: historicalVersions,
		}, http.StatusOK, nil
	}

	// We separate artifacts that belong to the latest workflow DAG from historical artifacts because we
	// want to show them separately on the UI.
	artifactIdsFromLatestWorkflowDags, err := h.CustomReader.GetArtifactIdsFromWorkflowDagIdsAndDownstreamOperatorIds(
		ctx,
		loadOperatorIds,
		latestWorkflowDagIds,
		h.Database,
	)
	if err != nil {
		return emptyResponse, http.StatusInternalServerError, errors.Wrap(err, "Unable to get artifact versions.")
	}

	latestArtifactIds := make(map[uuid.UUID]bool, len(artifactIdsFromLatestWorkflowDags))
	for _, artifactIdObject := range artifactIdsFromLatestWorkflowDags {
		latestArtifactIds[artifactIdObject.ArtifactId] = true
	}

	allArtifactIds := make([]uuid.UUID, 0, len(loadOperatorIds))

	for _, loadOperator := range loadOperatorMetadata {
		if _, ok := latestArtifactIds[loadOperator.ArtifactId]; ok {
			// If we reach here, it means this load operator corresponds to an artifact that belongs
			// to the latest workflow dag of a workflow.
			if _, ok := latestVersions[loadOperator.ArtifactId]; !ok {
				// If we reach here, it means `latestVersions` doesn't have the artifact id entry yet,
				// so we initialize the `artifactVersions` object with the workflow name and an empty
				// `Versions` map.
				allArtifactIds = append(allArtifactIds, loadOperator.ArtifactId)
				latestVersions[loadOperator.ArtifactId] = artifactVersions{
					WorkflowName: loadOperator.WorkflowName,
					WorkflowId:   loadOperator.WorkflowId,
					ArtifactName: loadOperator.ArtifactName,
					Versions:     make(map[uuid.UUID]artifactVersion),
				}
			}

			artifactVersionsObject := latestVersions[loadOperator.ArtifactId]
			artifactVersionsObject.LoadSpecs = append(artifactVersionsObject.LoadSpecs, *loadOperator.Spec.Load())

			latestVersions[loadOperator.ArtifactId] = artifactVersionsObject
		} else {
			if _, ok := historicalVersions[loadOperator.ArtifactId]; !ok {
				allArtifactIds = append(allArtifactIds, loadOperator.ArtifactId)
				historicalVersions[loadOperator.ArtifactId] = artifactVersions{
					WorkflowName: loadOperator.WorkflowName,
					Versions:     make(map[uuid.UUID]artifactVersion),
				}
			}

			artifactVersionsObject := historicalVersions[loadOperator.ArtifactId]
			artifactVersionsObject.LoadSpecs = append(artifactVersionsObject.LoadSpecs, *loadOperator.Spec.Load())

			historicalVersions[loadOperator.ArtifactId] = artifactVersionsObject
		}
	}

	artifactResults, err := h.CustomReader.GetArtifactResultsByArtifactIds(ctx, allArtifactIds, h.Database)
	if err != nil {
		return emptyResponse, http.StatusInternalServerError, errors.Wrap(err, "Unable to get artifact versions.")
	}

	// We track failed artifact versions and later on issue another query to fetch the
	// corresponding operator's error message.
	failedArtifactIdsMap := make(map[uuid.UUID]bool, len(allArtifactIds))
	failedWorkflowDagResultIds := make([]uuid.UUID, 0, len(artifactResults))

	// Create artifact versions and add timestamp and status metadata to it.
	// We leave the validation test result slice empty for now.
	for _, artifactResult := range artifactResults {
		if _, ok := latestVersions[artifactResult.ArtifactId]; ok {
			latestVersions[artifactResult.ArtifactId].Versions[artifactResult.WorkflowDagResultId] = artifactVersion{
				Timestamp: artifactResult.Timestamp.Unix(),
				Status:    artifactResult.Status,
				Checks:    nil,
			}
		} else {
			historicalVersions[artifactResult.ArtifactId].Versions[artifactResult.WorkflowDagResultId] = artifactVersion{
				Timestamp: artifactResult.Timestamp.Unix(),
				Status:    artifactResult.Status,
				Checks:    nil,
			}
		}

		if artifactResult.Status == shared.FailedExecutionStatus {
			failedArtifactIdsMap[artifactResult.ArtifactId] = true
			failedWorkflowDagResultIds = append(failedWorkflowDagResultIds, artifactResult.WorkflowDagResultId)
		}
	}

	failedArtifactIds := make([]uuid.UUID, 0, len(failedArtifactIdsMap))
	for failedArtifactId := range failedArtifactIdsMap {
		failedArtifactIds = append(failedArtifactIds, failedArtifactId)
	}

	checkResults, err := h.CustomReader.GetCheckResultsByArtifactIds(ctx, allArtifactIds, h.Database)
	if err != nil {
		return emptyResponse, http.StatusInternalServerError, errors.Wrap(err, "Unable to get artifact versions.")
	}

	// We now fill in the check test result. We can join the validation test result with the correct
	// artifact version by the workflow dag result id.
	for _, checkResult := range checkResults {
		checkResultObject := CheckResult{
			Name:     checkResult.Name,
			Status:   checkResult.Status,
			Metadata: checkResult.Metadata,
		}

		if _, ok := latestVersions[checkResult.ArtifactId]; ok {
			artifactVersionObject := latestVersions[checkResult.ArtifactId].Versions[checkResult.WorkflowDagResultId]
			artifactVersionObject.Checks = append(artifactVersionObject.Checks, checkResultObject)
			latestVersions[checkResult.ArtifactId].Versions[checkResult.WorkflowDagResultId] = artifactVersionObject
		} else {
			artifactVersionObject := historicalVersions[checkResult.ArtifactId].Versions[checkResult.WorkflowDagResultId]
			artifactVersionObject.Checks = append(artifactVersionObject.Checks, checkResultObject)
			historicalVersions[checkResult.ArtifactId].Versions[checkResult.WorkflowDagResultId] = artifactVersionObject
		}
	}

	// Issue query to fetch error message only when there is at least one failed artifact version.
	if len(failedArtifactIds) > 0 {
		failedOperatorResults, err := h.CustomReader.GetOperatorResultsByArtifactIdsAndWorkflowDagResultIds(
			ctx,
			failedArtifactIds,
			failedWorkflowDagResultIds,
			h.Database,
		)
		if err != nil {
			return emptyResponse, http.StatusInternalServerError, errors.Wrap(err, "Unable to get artifact versions.")
		}

		for _, failedOperatorResult := range failedOperatorResults {
			if _, ok := latestVersions[failedOperatorResult.ArtifactId]; ok {
				artifactVersionObject := latestVersions[failedOperatorResult.ArtifactId].Versions[failedOperatorResult.WorkflowDagResultId]
				artifactVersionObject.Error = failedOperatorResult.Metadata.Error
				latestVersions[failedOperatorResult.ArtifactId].Versions[failedOperatorResult.WorkflowDagResultId] = artifactVersionObject
			} else {
				artifactVersionObject := historicalVersions[failedOperatorResult.ArtifactId].Versions[failedOperatorResult.WorkflowDagResultId]
				artifactVersionObject.Error = failedOperatorResult.Metadata.Error
				historicalVersions[failedOperatorResult.ArtifactId].Versions[failedOperatorResult.WorkflowDagResultId] = artifactVersionObject
			}
		}
	}

	return getArtifactVersionsResponse{
		LatestVersions:     latestVersions,
		HistoricalVersions: historicalVersions,
	}, http.StatusOK, nil
}
