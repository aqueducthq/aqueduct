package server

import (
	"github.com/aqueducthq/aqueduct/cmd/server/handler"
	"github.com/aqueducthq/aqueduct/cmd/server/routes"
)

func (s *AqServer) Handlers() map[string]handler.Handler {
	return map[string]handler.Handler{
		routes.ArchiveNotificationRoute: &handler.ArchiveNotificationHandler{
			NotificationReader: s.NotificationReader,
			NotificationWriter: s.NotificationWriter,
			Database:           s.Database,
		},
		routes.ConnectIntegrationRoute: &handler.ConnectIntegrationHandler{
			Database:          s.Database,
			IntegrationWriter: s.IntegrationWriter,
			JobManager:        s.JobManager,
			Vault:             s.Vault,
			StorageConfig:     s.StorageConfig,
		},
		routes.DeleteWorkflowRoute: &handler.DeleteWorkflowHandler{
			Database:                s.Database,
			StorageConfig:           s.StorageConfig,
			JobManager:              s.JobManager,
			Vault:                   s.Vault,
			WorkflowReader:          s.WorkflowReader,
			WorkflowDagReader:       s.WorkflowDagReader,
			WorkflowDagEdgeReader:   s.WorkflowDagEdgeReader,
			WorkflowDagResultReader: s.WorkflowDagResultReader,
			OperatorReader:          s.OperatorReader,
			OperatorResultReader:    s.OperatorResultReader,
			ArtifactResultReader:    s.ArtifactResultReader,
			IntegrationReader:       s.IntegrationReader,

			WorkflowWriter:          s.WorkflowWriter,
			WorkflowDagWriter:       s.WorkflowDagWriter,
			WorkflowDagEdgeWriter:   s.WorkflowDagEdgeWriter,
			WorkflowDagResultWriter: s.WorkflowDagResultWriter,
			WorkflowWatcherWriter:   s.WorkflowWatcherWriter,
			OperatorWriter:          s.OperatorWriter,
			OperatorResultWriter:    s.OperatorResultWriter,
			ArtifactWriter:          s.ArtifactWriter,
			ArtifactResultWriter:    s.ArtifactResultWriter,
		},
		routes.EditWorkflowRoute: &handler.EditWorkflowHandler{
			Database:       s.Database,
			WorkflowReader: s.WorkflowReader,
			WorkflowWriter: s.WorkflowWriter,
			JobManager:     s.JobManager,
			Vault:          s.Vault,
			GithubManager:  s.GithubManager,
		},
		routes.ExportFunctionRoute: &handler.ExportFunctionHandler{
			Database:          s.Database,
			OperatorReader:    s.OperatorReader,
			WorkflowDagReader: s.WorkflowDagReader,
		},
		routes.GetArtifactResultRoute: &handler.GetArtifactResultHandler{
			Database:             s.Database,
			ArtifactReader:       s.ArtifactReader,
			ArtifactResultReader: s.ArtifactResultReader,
			WorkflowDagReader:    s.WorkflowDagReader,
		},
		routes.GetArtifactVersionsRoute: &handler.GetArtifactVersionsHandler{
			Database:     s.Database,
			CustomReader: s.CustomReader,
		},
		routes.GetNodePositionsRoute: &handler.GetNodePositionsHandler{},
		routes.GetOperatorResultRoute: &handler.GetOperatorResultHandler{
			Database:             s.Database,
			OperatorReader:       s.OperatorReader,
			OperatorResultReader: s.OperatorResultReader,
		},
		routes.GetUserProfileRoute: &handler.GetUserProfileHandler{},
		routes.ListWorkflowObjectsRoute: &handler.ListWorkflowObjectsHandler{
			Database:       s.Database,
			OperatorReader: s.OperatorReader,
			WorkflowReader: s.WorkflowReader,
		},
		routes.GetWorkflowRoute: &handler.GetWorkflowHandler{
			Database:                s.Database,
			ArtifactReader:          s.ArtifactReader,
			OperatorReader:          s.OperatorReader,
			UserReader:              s.UserReader,
			WorkflowReader:          s.WorkflowReader,
			WorkflowDagReader:       s.WorkflowDagReader,
			WorkflowDagEdgeReader:   s.WorkflowDagEdgeReader,
			WorkflowDagResultReader: s.WorkflowDagResultReader,
		},
		routes.ListBuiltinFunctionsRoute: &handler.ListBuiltinFunctionsHandler{
			StorageConfig: s.StorageConfig,
		},
		routes.ListIntegrationsRoute: &handler.ListIntegrationsHandler{
			Database:          s.Database,
			IntegrationReader: s.IntegrationReader,
		},
		routes.ListNotificationsRoute: &handler.ListNotificationsHandler{
			Database:           s.Database,
			NotificationReader: s.NotificationReader,
			WorkflowReader:     s.WorkflowReader,
		},
		routes.ListOperatorsForIntegrationRoute: &handler.ListOperatorsForIntegrationHandler{
			Database:       s.Database,
			OperatorReader: s.OperatorReader,
			CustomReader:   s.CustomReader,
		},
		routes.ListWorkflowsRoute: &handler.ListWorkflowsHandler{
			Database:       s.Database,
			WorkflowReader: s.WorkflowReader,
		},
		routes.PreviewTableRoute: &handler.PreviewTableHandler{
			Database:          s.Database,
			IntegrationReader: s.IntegrationReader,
			StorageConfig:     s.StorageConfig,
			JobManager:        s.JobManager,
			Vault:             s.Vault,
		},
		routes.PreviewRoute: &handler.PreviewHandler{
			Database:          s.Database,
			IntegrationReader: s.IntegrationReader,
			StorageConfig:     s.StorageConfig,
			GithubManager:     s.GithubManager,
			JobManager:        s.JobManager,
			Vault:             s.Vault,
		},
		routes.DiscoverRoute: &handler.DiscoverHandler{
			Database:          s.Database,
			CustomReader:      s.CustomReader,
			IntegrationReader: s.IntegrationReader,
			StorageConfig:     s.StorageConfig,
			JobManager:        s.JobManager,
			Vault:             s.Vault,
		},
		routes.CreateTableRoute: &handler.CreateTableHandler{
			Database:          s.Database,
			IntegrationReader: s.IntegrationReader,
			StorageConfig:     s.StorageConfig,
			JobManager:        s.JobManager,
			Vault:             s.Vault,
		},
		routes.RefreshWorkflowRoute: &handler.RefreshWorkflowHandler{
			Database:       s.Database,
			JobManager:     s.JobManager,
			GithubManager:  s.GithubManager,
			Vault:          s.Vault,
			WorkflowReader: s.WorkflowReader,
		},
		routes.RegisterWorkflowRoute: &handler.RegisterWorkflowHandler{
			Database:      s.Database,
			JobManager:    s.JobManager,
			GithubManager: s.GithubManager,
			Vault:         s.Vault,
			StorageConfig: s.StorageConfig,

			ArtifactReader:    s.ArtifactReader,
			IntegrationReader: s.IntegrationReader,
			OperatorReader:    s.OperatorReader,
			WorkflowReader:    s.WorkflowReader,

			ArtifactWriter:        s.ArtifactWriter,
			OperatorWriter:        s.OperatorWriter,
			WorkflowWriter:        s.WorkflowWriter,
			WorkflowDagWriter:     s.WorkflowDagWriter,
			WorkflowDagEdgeWriter: s.WorkflowDagEdgeWriter,
			WorkflowWatcherWriter: s.WorkflowWatcherWriter,
		},
		routes.ResetApiKeyRoute: &handler.ResetApiKeyHandler{
			Database:   s.Database,
			UserWriter: s.UserWriter,
		},
	}
}
