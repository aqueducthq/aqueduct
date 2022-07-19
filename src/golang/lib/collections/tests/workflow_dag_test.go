package tests

import (
	"context"
	"testing"

	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/collections/workflow_dag"
	"github.com/google/uuid"
	"github.com/stretchr/testify/require"
)

func seedWorkflowDag(t *testing.T, count int) []workflow_dag.DBWorkflowDag {
	numWorkflows := 2

	workflows := seedWorkflow(t, numWorkflows)
	workflowIds := randWorkflowIdsFromList(count, workflows)

	return seedWorkflowDagWithWorkflows(t, count, workflowIds)
}

// seedWorkflowDagWithWorkflows populates the workflow_dag table with count workflow dags where
// workflow_id is set to the values provided in workflowIds.
func seedWorkflowDagWithWorkflows(t *testing.T, count int, workflowIds []uuid.UUID) []workflow_dag.DBWorkflowDag {
	require.Len(t, workflowIds, count)

	workflowDags := make([]workflow_dag.DBWorkflowDag, 0, count)

	for i := 0; i < count; i++ {
		testWorkflowDag, err := writers.workflowDagWriter.CreateWorkflowDag(
			context.Background(),
			workflowIds[i],
			&shared.StorageConfig{
				Type: shared.S3StorageType,
				S3Config: &shared.S3Config{
					Region: "us-east-2",
					Bucket: "bucket-test",
				},
			},
			&shared.EngineConfig{
				Type:           shared.AqueductEngineType,
				AqueductConfig: &shared.AqueductConfig{},
			},
			db,
		)
		require.Nil(t, err)

		workflowDags = append(workflowDags, *testWorkflowDag)
	}

	require.Len(t, workflowDags, count)

	return workflowDags
}

func requireEqualWorkflowDags(t *testing.T, expected, actual []workflow_dag.DBWorkflowDag) {
	require.Equal(t, len(expected), len(actual))

	for _, expectedWorkflowDag := range expected {
		found := false
		for _, actualWorkflowDag := range actual {
			if expectedWorkflowDag.Id == actualWorkflowDag.Id {
				found = true
				requireDeepEqual(t, expectedWorkflowDag, actualWorkflowDag)
			}
		}
		require.True(t, found, "Unable to find workflow dag: %v", expectedWorkflowDag)
	}
}

// idsFromWorkflowDags returns the ids from the workflow dags provided.
func idsFromWorkflowDags(workflowDags []workflow_dag.DBWorkflowDag) []uuid.UUID {
	ids := make([]uuid.UUID, 0, len(workflowDags))
	for _, workflowDag := range workflowDags {
		ids = append(ids, workflowDag.Id)
	}
	return ids
}

func TestCreateWorkflowDag(t *testing.T) {
	defer resetDatabase(t)

	workflows := seedWorkflow(t, 1)

	expectedWorkflowDag := &workflow_dag.DBWorkflowDag{
		WorkflowId: workflows[0].Id,
		StorageConfig: shared.StorageConfig{
			Type: shared.S3StorageType,
			S3Config: &shared.S3Config{
				Region: "us-east-2",
				Bucket: "bucket-test",
			},
		},
		EngineConfig: shared.EngineConfig{
			Type:           shared.AqueductEngineType,
			AqueductConfig: &shared.AqueductConfig{},
		},
	}

	actualWorkflowDag, err := writers.workflowDagWriter.CreateWorkflowDag(
		context.Background(),
		expectedWorkflowDag.WorkflowId,
		&expectedWorkflowDag.StorageConfig,
		&expectedWorkflowDag.EngineConfig,
		db,
	)
	require.Nil(t, err)
	require.NotEqual(t, uuid.Nil, actualWorkflowDag.Id)

	expectedWorkflowDag.Id = actualWorkflowDag.Id
	expectedWorkflowDag.CreatedAt = actualWorkflowDag.CreatedAt

	requireDeepEqual(t, expectedWorkflowDag, actualWorkflowDag)
}

func TestGetWorkflowDagsByWorkflowId(t *testing.T) {
	defer resetDatabase(t)

	numWorkflows := 1
	numOtherWorkflows := 2
	numWorkflowDags := 3
	numOtherWorkflowDags := 2

	testWorkflows := seedWorkflow(t, numWorkflows)
	testWorkflowIds := randWorkflowIdsFromList(numWorkflowDags, testWorkflows)

	// Create workflow dags for test workflow
	testWorkflowDags := seedWorkflowDagWithWorkflows(t, numWorkflowDags, testWorkflowIds)

	otherWorkflows := seedWorkflow(t, numOtherWorkflows)
	otherWorkflowIds := randWorkflowIdsFromList(numOtherWorkflowDags, otherWorkflows)

	// Create workflow dags by "other" workflows
	seedWorkflowDagWithWorkflows(t, numOtherWorkflowDags, otherWorkflowIds)

	workflowDags, err := readers.workflowDagReader.GetWorkflowDagsByWorkflowId(context.Background(), testWorkflows[0].Id, db)
	require.Nil(t, err)
	requireEqualWorkflowDags(t, testWorkflowDags, workflowDags)
}

func TestGetLatestWorkflowDag(t *testing.T) {
	defer resetDatabase(t)

	numWorkflows := 1

	testWorkflows := seedWorkflow(t, numWorkflows)

	first := seedWorkflowDagWithWorkflows(t, 1, []uuid.UUID{testWorkflows[0].Id})
	last := seedWorkflowDagWithWorkflows(t, 1, []uuid.UUID{testWorkflows[0].Id})

	firstDag := first[0]
	lastDag := last[0]

	require.True(t, lastDag.CreatedAt.After(firstDag.CreatedAt))

	latestDag, err := readers.workflowDagReader.GetLatestWorkflowDag(context.Background(), testWorkflows[0].Id, db)
	require.Nil(t, err)

	requireDeepEqual(t, lastDag, *latestDag)
}

func TestGetWorkflowDagByWorkflowDagResultId(t *testing.T) {
	defer resetDatabase(t)

	numWorkflowDags := 1
	numWorkflowDagResults := 2

	testWorkflowDags := seedWorkflowDag(t, numWorkflowDags)
	testDagIds := randWorkflowDagIdsFromList(numWorkflowDagResults, testWorkflowDags)

	testDagResults := seedWorkflowDagResultWithDags(t, numWorkflowDagResults, testDagIds)

	workflowDag, err := readers.workflowDagReader.GetWorkflowDagByWorkflowDagResultId(
		context.Background(),
		testDagResults[0].Id,
		db,
	)
	require.Nil(t, err)

	requireDeepEqual(t, testWorkflowDags[0], *workflowDag)
}

func TestGetWorkflowDagsByOperatorId(t *testing.T) {
	defer resetDatabase(t)

	numTestOperators := 3
	numOtherOperators := 2
	numWorkflowDags := 2

	testOperators := seedOperator(t, numTestOperators)
	otherOperators := seedOperator(t, numOtherOperators)

	workflowDags := seedWorkflowDag(t, numWorkflowDags)

	testEdges := map[uuid.UUID]uuid.UUID{
		testOperators[0].Id: testOperators[2].Id,
		testOperators[1].Id: testOperators[2].Id,
	}
	otherEdges := map[uuid.UUID]uuid.UUID{
		otherOperators[0].Id: otherOperators[1].Id,
	}

	seedWorkflowDagEdgeWithDagId(t, testEdges, workflowDags[0].Id)
	seedWorkflowDagEdgeWithDagId(t, otherEdges, workflowDags[1].Id)

	actualWorkflowDags, err := readers.workflowDagReader.GetWorkflowDagsByOperatorId(
		context.Background(),
		testOperators[1].Id,
		db,
	)
	require.Nil(t, err)

	requireEqualWorkflowDags(t, workflowDags[:1], actualWorkflowDags)
}

func TestDeleteWorkflowDags(t *testing.T) {
	defer resetDatabase(t)

	toDeleteDags := seedWorkflowDag(t, 2)
	toDeleteIds := idsFromWorkflowDags(toDeleteDags)

	err := writers.workflowDagWriter.DeleteWorkflowDags(context.Background(), toDeleteIds, db)
	require.Nil(t, err)

	dags, err := readers.workflowDagReader.GetWorkflowDags(context.Background(), toDeleteIds, db)
	require.Nil(t, err)
	require.Empty(t, dags)
}
