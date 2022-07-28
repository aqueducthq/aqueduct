package routes

// Please sort the route by their VALUEs
const (
	GetArtifactVersionsRoute = "/api/artifact_versions"
	GetArtifactResultRoute   = "/api/artifact_result/{workflowDagResultId}/{artifactId}"

	ListBuiltinFunctionsRoute = "/api/builtinFunctions"
	GetFunctionRoute          = "/api/function/{functionId}"
	ExportFunctionRoute       = "/api/function/{operatorId}/export"

	ListIntegrationsRoute            = "/api/integrations"
	ConnectIntegrationRoute          = "/api/integration/connect"
	DeleteIntegrationRoute           = "/api/integration/{integrationId}/delete"
	DiscoverRoute                    = "/api/integration/{integrationId}/discover"
	IntegrationObjectsRoute          = "/api/integration/{integrationId}/objects"
	CreateTableRoute                 = "/api/integration/{integrationId}/create"
	PreviewTableRoute                = "/api/integration/{integrationId}/preview_table"
	ListOperatorsForIntegrationRoute = "/api/integration/{integrationId}/operators"

	ResetApiKeyRoute = "/api/keys/reset" // nolint:gosec

	ListNotificationsRoute   = "/api/notifications"
	ArchiveNotificationRoute = "/api/notifications/{notificationId}/archive"

	GetOperatorResultRoute = "/api/operator_result/{workflowDagResultId}/{operatorId}"

	GetNodePositionsRoute = "/api/positioning"
	PreviewRoute          = "/api/preview"

	GetUserProfileRoute = "/api/user"

	ListWorkflowsRoute       = "/api/workflows"
	RegisterWorkflowRoute    = "/api/workflow/register"
	GetWorkflowRoute         = "/api/workflow/{workflowId}"
	ListWorkflowObjectsRoute = "/api/workflow/{workflowId}/objects"
	DeleteWorkflowRoute      = "/api/workflow/{workflowId}/delete"
	EditWorkflowRoute        = "/api/workflow/{workflowId}/edit"
	RefreshWorkflowRoute     = "/api/workflow/{workflowId}/refresh"
	UnwatchWorkflowRoute     = "/api/workflow/{workflowId}/unwatch"
	WatchWorkflowRoute       = "/api/workflow/{workflowId}/watch"
)
