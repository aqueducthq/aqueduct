package handler

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/aqueducthq/aqueduct/cmd/server/request"
	"github.com/aqueducthq/aqueduct/cmd/server/routes"
	"github.com/aqueducthq/aqueduct/lib/airflow"
	"github.com/aqueducthq/aqueduct/lib/collections/integration"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	postgres_utils "github.com/aqueducthq/aqueduct/lib/collections/utils"
	aq_context "github.com/aqueducthq/aqueduct/lib/context"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/aqueducthq/aqueduct/lib/job"
	"github.com/aqueducthq/aqueduct/lib/vault"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector/auth"
	"github.com/aqueducthq/aqueduct/lib/workflow/utils"
	"github.com/dropbox/godropbox/errors"
	"github.com/google/uuid"
)

const (
	pollAuthenticateInterval = 500 * time.Millisecond
	pollAuthenticateTimeout  = 2 * time.Minute
)

// ConnectIntegrationHandler connects a new integration for the organization.
type ConnectIntegrationHandler struct {
	PostHandler

	Database          database.Database
	IntegrationWriter integration.Writer
	Vault             vault.Vault
	JobManager        job.JobManager
	StorageConfig     *shared.StorageConfig
}

func (*ConnectIntegrationHandler) Headers() []string {
	return []string{
		routes.IntegrationNameHeader,
		routes.IntegrationServiceHeader,
		routes.IntegrationConfigHeader,
	}
}

type ConnectIntegrationArgs struct {
	*aq_context.AqContext
	Name     string              // User specified name for the integration
	Service  integration.Service // Name of the service to connect (e.g. Snowflake, Postgres)
	Config   auth.Config         // Integration config
	UserOnly bool                // Whether the integration is only accessible by the user or the entire org
}

type ConnectIntegrationResponse struct{}

func (*ConnectIntegrationHandler) Name() string {
	return "ConnectIntegration"
}

func (h *ConnectIntegrationHandler) Prepare(r *http.Request) (interface{}, int, error) {
	aqContext, statusCode, err := aq_context.ParseAqContext(r.Context())
	if err != nil {
		return nil, statusCode, errors.Wrap(err, "Unable to connect integration.")
	}

	service, name, configMap, userOnly, err := request.ParseIntegrationConfigFromRequest(r)
	if err != nil {
		return nil, http.StatusBadRequest, errors.Wrap(err, "Unable to connect integration.")
	}

	if service == integration.Github || service == integration.GoogleSheets {
		return nil, http.StatusBadRequest, errors.Newf("%s integration type is currently not supported", service)
	}

	config := auth.NewStaticConfig(configMap)

	return &ConnectIntegrationArgs{
		AqContext: aqContext,
		Service:   service,
		Name:      name,
		Config:    config,
		UserOnly:  userOnly,
	}, http.StatusOK, nil
}

func (h *ConnectIntegrationHandler) Perform(ctx context.Context, interfaceArgs interface{}) (interface{}, int, error) {
	args := interfaceArgs.(*ConnectIntegrationArgs)

	emptyResp := ConnectIntegrationResponse{}

	// Validate integration config
	statusCode, err := ValidateConfig(ctx, args, h.JobManager, h.StorageConfig)
	if err != nil {
		return emptyResp, statusCode, err
	}

	if statusCode, err := ConnectIntegration(ctx, args, h.IntegrationWriter, h.Database, h.Vault); err != nil {
		return emptyResp, statusCode, err
	}

	return emptyResp, http.StatusOK, nil
}

// ConnectIntegration connects a new integration specified by `args`. It returns a status code for the request
// and an error, if any.
func ConnectIntegration(
	ctx context.Context,
	args *ConnectIntegrationArgs,
	integrationWriter integration.Writer,
	db database.Database,
	vaultObject vault.Vault,
) (int, error) {
	// Extract non-confidential config
	publicConfig := args.Config.PublicConfig()

	var integrationObject *integration.Integration
	var err error
	if args.UserOnly {
		// This is a user-specific integration
		integrationObject, err = integrationWriter.CreateIntegrationForUser(
			ctx,
			args.OrganizationId,
			args.Id,
			args.Service,
			args.Name,
			(*postgres_utils.Config)(&publicConfig),
			true,
			db,
		)
	} else {
		integrationObject, err = integrationWriter.CreateIntegration(
			ctx,
			args.OrganizationId,
			args.Service,
			args.Name,
			(*postgres_utils.Config)(&publicConfig),
			true,
			db,
		)
	}
	if err != nil {
		return http.StatusInternalServerError, errors.Wrap(err, "Unable to connect integration.")
	}

	// Store config (including confidential information) as k8s secret
	if err := auth.WriteConfigToSecret(
		ctx,
		integrationObject.Id,
		args.Config,
		vaultObject,
	); err != nil {
		// TODO ENG-498: Rollback integration write
		return http.StatusInternalServerError, errors.Wrap(err, "Unable to connect integration.")
	}

	return http.StatusOK, nil
}

// ValidateConfig authenticates the config provided.
// It returns a status code and an error, if any.
func ValidateConfig(
	ctx context.Context,
	args *ConnectIntegrationArgs,
	jobManager job.JobManager,
	storageConfig *shared.StorageConfig,
) (int, error) {
	if args.Service == integration.Airflow {
		// Airflow authentication is performed via the Go client
		// instead of the Python client, so we don't launch a job for it.
		return validateAirflowConfig(ctx, args)
	}

	// Schedule authenticate job
	jobMetadataPath := fmt.Sprintf("authenticate-%s", args.RequestId)

	defer func() {
		// Delete storage files created for authenticate job metadata
		go utils.CleanupStorageFiles(ctx, storageConfig, []string{jobMetadataPath})
	}()

	jobName := fmt.Sprintf("authenticate-operator-%s", uuid.New().String())
	jobSpec := job.NewAuthenticateSpec(
		jobName,
		storageConfig,
		jobMetadataPath,
		args.Service,
		args.Config,
	)

	if err := jobManager.Launch(ctx, jobName, jobSpec); err != nil {
		return http.StatusInternalServerError, errors.Wrap(err, "Unable to launch authenticate job.")
	}

	jobStatus, err := job.PollJob(ctx, jobName, jobManager, pollAuthenticateInterval, pollAuthenticateTimeout)
	if err != nil {
		return http.StatusInternalServerError, errors.Wrap(err, "Unable to connect integration.")
	}

	if jobStatus == shared.SucceededExecutionStatus {
		// Authentication was successful
		return http.StatusOK, nil
	}

	// Authentication failed, so we need to fetch the error message from storage
	var execState shared.ExecutionState
	if err := utils.ReadFromStorage(
		ctx,
		storageConfig,
		jobMetadataPath,
		&execState,
	); err != nil {
		return http.StatusInternalServerError, errors.Wrap(err, "Unable to connect integration.")
	}

	if execState.Error != nil {
		return http.StatusBadRequest, errors.Newf(
			"Unable to authenticate.\n%s\n%s",
			execState.Error.Tip,
			execState.Error.Context,
		)
	}

	return http.StatusInternalServerError, errors.New(
		"Unable to authenticate credentials, we couldn't obtain more context at this point.",
	)
}

// validateAirflowConfig authenticates the Airflow config provided.
// It returns a status code and an error, if any.
func validateAirflowConfig(
	ctx context.Context,
	args *ConnectIntegrationArgs,
) (int, error) {
	if err := airflow.Authenticate(ctx, args.Config); err != nil {
		return http.StatusBadRequest, err
	}

	return http.StatusOK, nil
}
