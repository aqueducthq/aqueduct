package tests

import (
	"context"
	"testing"

	"github.com/aqueducthq/aqueduct/lib/collections/operator/connector"

	"github.com/aqueducthq/aqueduct/cmd/server/queries"
	"github.com/aqueducthq/aqueduct/lib/collections/artifact"
	"github.com/aqueducthq/aqueduct/lib/collections/integration"
	"github.com/aqueducthq/aqueduct/lib/collections/operator"
	"github.com/google/uuid"
	"github.com/stretchr/testify/require"
)

func TestGetLoadOperatorSpecByOrganization(t *testing.T) {
	defer resetDatabase(t)

	dags := seedWorkflowDag(t, 1)
	testDag := dags[0]

	testWorkflow, err := readers.workflowReader.GetWorkflow(context.Background(), testDag.WorkflowId, db)
	require.Nil(t, err)

	testUser, err := readers.userReader.GetUser(context.Background(), testWorkflow.UserId, db)
	require.Nil(t, err)

	testArtifact, err := writers.artifactWriter.CreateArtifact(
		context.Background(),
		randString(5),
		randString(10),
		&artifact.Spec{artifact.TabularType},
		db,
	)
	require.Nil(t, err)

	testOps := seedOperatorWithSpecs(t, 1, []operator.Spec{
		*operator.NewSpecFromLoad(connector.Load{
			Service:       integration.Postgres,
			IntegrationId: uuid.New(),
			Parameters:    &connector.PostgresLoadParams{connector.RelationalDBLoadParams{Table: "test"}},
		}),
	})

	loadOp := testOps[0]
	require.True(t, loadOp.Spec.IsLoad())

	seedWorkflowDagEdgeWithDagId(
		t,
		map[uuid.UUID]uuid.UUID{
			testArtifact.Id: loadOp.Id,
		},
		testDag.Id,
	)

	expectedResponse := queries.LoadOperatorSpecResponse{
		ArtifactId:     testArtifact.Id,
		ArtifactName:   testArtifact.Name,
		LoadOperatorId: loadOp.Id,
		WorkflowName:   testWorkflow.Name,
		WorkflowId:     testWorkflow.Id,
		Spec:           loadOp.Spec,
	}

	loadOpSpecResp, err := readers.serverReader.GetLoadOperatorSpecByOrganization(context.Background(), testUser.OrganizationId, db)
	require.Nil(t, err)
	require.Len(t, loadOpSpecResp, 1)

	requireDeepEqual(t, expectedResponse, loadOpSpecResp[0])
}
