package airflow

import (
	"fmt"
	"testing"

	"github.com/aqueducthq/aqueduct/lib/collections/operator"
	"github.com/google/uuid"
	"github.com/stretchr/testify/require"
)

func TestComputeEdges(t *testing.T) {
	// Tests the following workflow DAG
	/*
		OP_a -------> artf_1
		                    \
		OP_b -----> artf_2 -> OP_d --> artf_4 --> OP_e --> artf_5
							/                  \
		OP_c -------> artf_3                    \
												OP_f ---> artf_6
	*/

	operators := []string{"A", "B", "C", "D", "E", "F"}
	artifacts := []string{"1", "2", "3", "4", "5", "6"}

	operatorsToId := make(map[string]uuid.UUID, len(operators))
	for _, op := range operators {
		operatorsToId[op] = uuid.New()
	}
	artifactsToId := make(map[string]uuid.UUID, len(artifacts))
	for _, artifact := range artifacts {
		artifactsToId[artifact] = uuid.New()
	}

	fmt.Println(operatorsToId)
	fmt.Println(artifactsToId)

	testOperators := map[uuid.UUID]operator.DBOperator{
		operatorsToId["A"]: {
			Id:      operatorsToId["A"],
			Inputs:  nil,
			Outputs: []uuid.UUID{artifactsToId["1"]},
		},
		operatorsToId["B"]: {
			Id:      operatorsToId["B"],
			Inputs:  nil,
			Outputs: []uuid.UUID{artifactsToId["2"]},
		},
		operatorsToId["C"]: {
			Id:      operatorsToId["C"],
			Inputs:  nil,
			Outputs: []uuid.UUID{artifactsToId["3"]},
		},
		operatorsToId["D"]: {
			Id:      operatorsToId["D"],
			Inputs:  []uuid.UUID{artifactsToId["1"], artifactsToId["2"], artifactsToId["3"]},
			Outputs: []uuid.UUID{artifactsToId["4"]},
		},
		operatorsToId["E"]: {
			Id:      operatorsToId["E"],
			Inputs:  []uuid.UUID{artifactsToId["4"]},
			Outputs: []uuid.UUID{artifactsToId["5"]},
		},
		operatorsToId["F"]: {
			Id:      operatorsToId["F"],
			Inputs:  []uuid.UUID{artifactsToId["4"]},
			Outputs: []uuid.UUID{artifactsToId["6"]},
		},
	}

	testOperatorToTask := map[uuid.UUID]string{
		operatorsToId["A"]: "taskA",
		operatorsToId["B"]: "taskB",
		operatorsToId["C"]: "taskC",
		operatorsToId["D"]: "taskD",
		operatorsToId["E"]: "taskE",
		operatorsToId["F"]: "taskF",
	}

	expectedEdges := map[string][]string{
		"taskA": {"taskD"},
		"taskB": {"taskD"},
		"taskC": {"taskD"},
		"taskD": {"taskF", "taskE"},
	}

	edges, err := computeEdges(testOperators, testOperatorToTask)

	require.Nil(t, err)
	require.Equal(t, expectedEdges, edges)
}
