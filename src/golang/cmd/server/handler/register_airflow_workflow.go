package handler

import (
	"context"
	"net/http"

	"github.com/aqueducthq/aqueduct/cmd/server/request"
	aq_context "github.com/aqueducthq/aqueduct/lib/context"
	"github.com/aqueducthq/aqueduct/lib/database"
	dag_utils "github.com/aqueducthq/aqueduct/lib/workflow/dag"
	operator_utils "github.com/aqueducthq/aqueduct/lib/workflow/operator"
	"github.com/aqueducthq/aqueduct/lib/workflow/utils"
	"github.com/dropbox/godropbox/errors"
	"github.com/google/uuid"
)

// Route: /workflow/register_airflow
// Method: POST
// Params: none
// Request
//	Headers:
//		`api-key`: user's API Key
//	Body:
//		`dag`: a serialized `workflow_dag` object
//		`<operator_id>`: zip file associated with operator for the `operator_id`.
//  	`<operator_id>`: ... (more operator files)
// Response:
//		`file`: a Python file that defines the Airflow DAG

type RegisterAirflowWorkflowHandler struct {
	RegisterWorkflowHandler
}

type registerAirflowWorkflowArgs struct {
	registerWorkflowArgs
}

type registerAirflowWorkflowResponse struct {
	// The newly registered workflow's id.
	Id   uuid.UUID `json:"id"`
	File string    `json:"file"`
}

func (*RegisterAirflowWorkflowHandler) Name() string {
	return "RegisterAirflowWorkflow"
}

func (h *RegisterAirflowWorkflowHandler) Prepare(r *http.Request) (interface{}, int, error) {
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
		return nil, statusCode, errors.Wrap(err, "Unable to register workflow.")
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

	collidingWorkflow, err := h.WorkflowReader.GetWorkflowByName(
		r.Context(),
		dagSummary.Dag.Metadata.UserId,
		dagSummary.Dag.Metadata.Name,
		h.Database,
	)
	if err != nil {
		return nil, http.StatusInternalServerError, errors.Wrap(err, "Unexpected error occurred when checking for existing workflows.")
	}

	if collidingWorkflow != nil {
		return nil, http.StatusBadRequest, errors.New("Updates are not currently supported for Workflows running on Airflow")
	}

	if err := dag_utils.Validate(
		dagSummary.Dag,
	); err != nil {
		if _, ok := dag_utils.ValidationErrors[err]; !ok {
			return nil, http.StatusInternalServerError, errors.Wrap(err, "Internal system error occurred while validating the DAG.")
		} else {
			return nil, http.StatusBadRequest, err
		}
	}

	return &registerAirflowWorkflowArgs{
		registerWorkflowArgs: registerWorkflowArgs{
			AqContext:                aqContext,
			workflowDag:              dagSummary.Dag,
			operatorIdToFileContents: dagSummary.FileContentsByOperatorUUID,
		},
	}, http.StatusOK, nil
}

func (h *RegisterAirflowWorkflowHandler) Perform(ctx context.Context, interfaceArgs interface{}) (interface{}, int, error) {
	args := interfaceArgs.(*registerWorkflowArgs)

	emptyResp := registerAirflowWorkflowResponse{}

	if _, err := operator_utils.UploadOperatorFiles(ctx, args.workflowDag, args.operatorIdToFileContents); err != nil {
		return emptyResp, http.StatusInternalServerError, errors.Wrap(err, "Unable to create workflow.")
	}

	txn, err := h.Database.BeginTx(ctx)
	if err != nil {
		return emptyResp, http.StatusInternalServerError, errors.Wrap(err, "Unable to create workflow.")
	}
	defer database.TxnRollbackIgnoreErr(ctx, txn)

	workflowId, err := utils.WriteWorkflowDagToDatabase(
		ctx,
		args.workflowDag,
		h.WorkflowReader,
		h.WorkflowWriter,
		h.WorkflowDagWriter,
		h.OperatorReader,
		h.OperatorWriter,
		h.WorkflowDagEdgeWriter,
		h.ArtifactReader,
		h.ArtifactWriter,
		txn,
	)
	if err != nil {
		return emptyResp, http.StatusInternalServerError, errors.Wrap(err, "Unable to create workflow.")
	}

	args.workflowDag.Metadata.Id = workflowId

	airflowFile, err := airflow.RegisterWorkflow(
		ctx,
		args.workflowDag,
		h.StorageConfig,
		h.JobManager,
		h.Vault,
		txn,
		h.WorkflowDagWriter,
	)
	if err != nil {
		return emptyResp, http.StatusInternalServerError, errors.Wrap(err, "Unable to create workflow.")
	}

	if err := txn.Commit(ctx); err != nil {
		return emptyResp, http.StatusInternalServerError, errors.Wrap(err, "Unable to create workflow.")
	}

	watchWorkflowArgs := &watchWorkflowArgs{
		AqContext:  args.AqContext,
		workflowId: workflowId,
	}

	_, _, err = (&WatchWorkflowHandler{
		Database:              h.Database,
		WorkflowReader:        h.WorkflowReader,
		WorkflowWatcherWriter: h.WorkflowWatcherWriter,
	}).Perform(ctx, watchWorkflowArgs)
	if err != nil {
		return emptyResp, http.StatusInternalServerError, errors.Wrap(err, "Unable to add user who created the workflow to watch.")
	}

	return &registerAirflowWorkflowResponse{
		Id:   workflowId,
		File: airflowFile,
	}, http.StatusOK, nil
}
