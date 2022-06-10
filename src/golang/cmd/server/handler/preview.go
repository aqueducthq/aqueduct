package handler

import (
	"context"
	"net/http"
	"strconv"
	"fmt"

	"github.com/aqueducthq/aqueduct/cmd/server/request"
	"github.com/aqueducthq/aqueduct/lib/collections/artifact"
	"github.com/aqueducthq/aqueduct/lib/collections/artifact_result"
	"github.com/aqueducthq/aqueduct/lib/collections/integration"
	"github.com/aqueducthq/aqueduct/lib/collections/operator_result"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	aq_context "github.com/aqueducthq/aqueduct/lib/context"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/aqueducthq/aqueduct/lib/job"
	"github.com/aqueducthq/aqueduct/lib/storage"
	"github.com/aqueducthq/aqueduct/lib/vault"
	dag_utils "github.com/aqueducthq/aqueduct/lib/workflow/dag"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector/github"
	"github.com/aqueducthq/aqueduct/lib/workflow/orchestrator"
	"github.com/aqueducthq/aqueduct/lib/workflow/utils"
	"github.com/dropbox/godropbox/errors"
	"github.com/google/uuid"
)

// Route: /preview
// Method: POST
// Params: none
// Request:
//	Headers:
//		`api-key`: user's API Key
//	Body:
//		"dag": a serialized `workflow_dag` object
//		"<operator_id>": zip file associated with operator for the `operator_id`.
//  	"<operator_id>": ... (more operator files)
// Response:
//	Body:
//		serialized `previewResponse` object consisting of overall status and results for all executed operators / artifacts.

const previewPollIntervalMillisec = 100

type previewArgs struct {
	*aq_context.AqContext
	DagSummary *request.DagSummary
	// Add list of IDs
}

type previewOperatorResponse struct {
	Status shared.ExecutionStatus `json:"status"`
	Logs   map[string]string      `json:"logs"`
	ErrMsg string                 `json:"err_msg"`
}

type previewFloatArtifactResponse struct {
	Val float64 `json:"val"`
}

type previewBoolArtifactResponse struct {
	Passed bool `json:"passed"`
}

type previewParamArtifactResponse struct {
	Val string `json:"val"`
}

type previewTableArtifactResponse struct {
	TableSchema []map[string]string `json:"table_schema"`
	Data        string                   `json:"data"`
}

type previewArtifactResponse struct {
	Table  *previewTableArtifactResponse `json:"table"`
	Metric *previewFloatArtifactResponse `json:"metric"`
	Check  *previewBoolArtifactResponse  `json:"check"`
	Param  *previewParamArtifactResponse `json:"param"`
}

type previewResponse struct {
	Status          shared.ExecutionStatus                `json:"status"`
	OperatorResults map[uuid.UUID]previewOperatorResponse `json:"operator_results"`
	ArtifactResults map[uuid.UUID]previewArtifactResponse `json:"artifact_results"`
}

type PreviewHandler struct {
	PostHandler

	Database          database.Database
	IntegrationReader integration.Reader
	StorageConfig     *shared.StorageConfig
	JobManager        job.JobManager
	GithubManager     github.Manager
	Vault             vault.Vault
}

func (*PreviewHandler) Name() string {
	return "Preview"
}

func (h *PreviewHandler) Prepare(r *http.Request) (interface{}, int, error) {
	aqContext, statusCode, err := aq_context.ParseAqContext(r.Context())
	if err != nil {
		return nil, statusCode, err
	}

	dagSummary, statusCode, err := request.ParseDagSummaryFromRequest(
		r,
		aqContext.Id,
		h.GithubManager,
		h.StorageConfig,
	)
	if err != nil {
		return nil, statusCode, err
	}

	ok, err := dag_utils.ValidateDagOperatorIntegrationOwnership(
		r.Context(),
		dagSummary.Dag.Operators,
		aqContext.OrganizationId,
		h.IntegrationReader,
		h.Database,
	)
	if err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unexpected error during integration ownership validation.")
	}
	if !ok {
		return nil, http.StatusBadRequest, errors.Wrap(err, "The organization does not own the integrations defined in the Dag.")
	}

	removeLoadOperators(dagSummary)

	if err := dag_utils.Validate(
		dagSummary.Dag,
	); err != nil {
		if _, ok := dag_utils.ValidationErrors[err]; !ok {
			return nil, http.StatusInternalServerError, errors.Wrap(err, "Internal system error occured while validating the DAG.")
		} else {
			return nil, http.StatusBadRequest, err
		}
	}

	return &previewArgs{
		AqContext:  aqContext,
		DagSummary: dagSummary,
	}, http.StatusOK, nil
}

func (h *PreviewHandler) Perform(ctx context.Context, interfaceArgs interface{}) (interface{}, int, error) {
	args := interfaceArgs.(*previewArgs)
	errorRespPtr := &previewResponse{Status: shared.FailedExecutionStatus}
	dagSummary := args.DagSummary

	operatorStoragePaths, err := operator.UploadOperatorFiles(ctx, dagSummary.Dag, dagSummary.FileContentsByOperatorUUID)
	if err != nil {
		return errorRespPtr, http.StatusInternalServerError, errors.Wrap(err, "Error uploading function files.")
	}

	defer utils.CleanupStorageFiles(ctx, h.StorageConfig, operatorStoragePaths)

	workflowPaths := utils.GenerateWorkflowStoragePaths(dagSummary.Dag)
	defer utils.CleanupWorkflowStorageFiles(ctx, workflowPaths, h.StorageConfig, false /* also clean up artifact contents */)

	status, err := orchestrator.Preview(
		ctx,
		dagSummary.Dag,
		workflowPaths,
		previewPollIntervalMillisec,
		h.JobManager,
		h.Vault,
	)
	if err != nil {
		return errorRespPtr, http.StatusInternalServerError, errors.Wrap(err, "Error executing the workflow.")
	}

	operatorResults := deserializeOperatorResponses(ctx, workflowPaths, h.StorageConfig)

	// We should not include artifact results for operators that failed.
	artifactsToSkipFetch := map[uuid.UUID]bool{}
	for opId, opResult := range operatorResults {
		if opResult.Status == shared.FailedExecutionStatus {
			for _, artifactId := range dagSummary.Dag.Operators[opId].Outputs {
				artifactsToSkipFetch[artifactId] = true
			}
		}
	}
	artifactResults, err := deserializeArtifactResponses(ctx, workflowPaths, h.StorageConfig, dagSummary.Dag.Artifacts, artifactsToSkipFetch)
	if err != nil {
		return errorRespPtr, http.StatusInternalServerError, errors.Wrap(err, "Error deserializing execution results.")
	}
	return &previewResponse{
		Status:          status,
		OperatorResults: operatorResults,
		ArtifactResults: artifactResults,
	}, http.StatusOK, nil
}

func deserializeOperatorResponses(
	ctx context.Context,
	workflowStoragePaths *utils.WorkflowStoragePaths,
	storageConfig *shared.StorageConfig,
) map[uuid.UUID]previewOperatorResponse {
	responses := make(map[uuid.UUID]previewOperatorResponse, len(workflowStoragePaths.OperatorMetadataPaths))
	for id, path := range workflowStoragePaths.OperatorMetadataPaths {
		var operatorMetadata operator_result.Metadata
		err := utils.ReadFromStorage(ctx, storageConfig, path, &operatorMetadata)
		if err != nil {
			responses[id] = previewOperatorResponse{
				Status: shared.FailedExecutionStatus,
				ErrMsg: "Unable to retrieve metadata for this operator. The workflow might have failed before executing this operator.",
			}
			continue
		}

		status := shared.FailedExecutionStatus
		if len(operatorMetadata.Error) == 0 {
			status = shared.SucceededExecutionStatus
		}

		responses[id] = previewOperatorResponse{
			Status: status,
			Logs:   operatorMetadata.Logs,
			ErrMsg: operatorMetadata.Error,
		}
	}
	return responses
}

func deserializeArtifactResponses(
	ctx context.Context,
	workflowStoragePaths *utils.WorkflowStoragePaths,
	storageConfig *shared.StorageConfig,
	dagArtifacts map[uuid.UUID]artifact.Artifact,
	artifactsToSkipFetch map[uuid.UUID]bool,
) (map[uuid.UUID]previewArtifactResponse, error) {
	responses := make(map[uuid.UUID]previewArtifactResponse, len(workflowStoragePaths.ArtifactPaths))
	for id, contentPath := range workflowStoragePaths.ArtifactPaths {
		if _, ok := artifactsToSkipFetch[id]; ok {
			continue
		}

		content, err := storage.NewStorage(storageConfig).Get(ctx, contentPath)
		if err != nil {
			return nil, err
		}

		artifactSpec := dagArtifacts[id].Spec
		if artifactSpec.IsFloat() {
			val, err := strconv.ParseFloat(string(content), 32)
			if err != nil {
				return nil, err
			}

			responses[id] = previewArtifactResponse{
				Metric: &previewFloatArtifactResponse{
					Val: val,
				},
			}
		} else if artifactSpec.IsBool() {
			passed, err := strconv.ParseBool(string(content))
			if err != nil {
				return nil, err
			}

			responses[id] = previewArtifactResponse{
				Check: &previewBoolArtifactResponse{
					Passed: passed,
				},
			}
		} else if artifactSpec.IsJson() {
			responses[id] = previewArtifactResponse{
				Param: &previewParamArtifactResponse{
					Val: string(content),
				},
			}
		} else if artifactSpec.IsTable() {

			var metadata artifact_result.Metadata
			err := utils.ReadFromStorage(ctx, storageConfig, workflowStoragePaths.ArtifactMetadataPaths[id], &metadata)
			if err != nil {
				metadata = artifact_result.Metadata{}
			}
			fmt.Println("WE GOT THE METADATA AND IT IS THIS: ")

			fmt.Println(metadata.Schema)
			fmt.Println(metadata.SystemMetadata)
			fmt.Println("===========")
			responses[id] = previewArtifactResponse{
				Table: &previewTableArtifactResponse{
					TableSchema: metadata.Schema,
					Data:        string(content),
				},
			}
		} else {
			return nil, errors.Newf("Unsupported artifact spec %s", artifactSpec.Type())
		}
	}
	return responses, nil
}

func removeLoadOperators(dagSummary *request.DagSummary) {
	removeList := make([]uuid.UUID, 0, len(dagSummary.Dag.Operators))

	for id, op := range dagSummary.Dag.Operators {
		if op.Spec.IsLoad() {
			removeList = append(removeList, id)
		}
	}

	for _, id := range removeList {
		delete(dagSummary.Dag.Operators, id)
	}
}
