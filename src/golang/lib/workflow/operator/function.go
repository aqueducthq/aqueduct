package operator

import (
	"fmt"

	db_artifact "github.com/aqueducthq/aqueduct/lib/collections/artifact"
	"github.com/aqueducthq/aqueduct/lib/job"
	"github.com/dropbox/godropbox/errors"
	"github.com/google/uuid"
)

type functionOperatorImpl struct {
	baseFunctionOperator
}

func generateFunctionJobName() string {
	return fmt.Sprintf("function-operator-%s", uuid.New().String())
}

func newFunctionOperator(
	base baseFunctionOperator,
) (Operator, error) {
	base.jobName = generateFunctionJobName()

	inputs := base.inputs
	outputs := base.outputs

	if len(outputs) == 0 {
		return nil, errWrongNumOutputs
	}

	for _, inputArtifact := range inputs {
		if inputArtifact.Type() != db_artifact.TableType && inputArtifact.Type() != db_artifact.JsonType {
			return nil, errors.New("Inputs to function operator must be Table or Parameter Artifacts.")
		}
	}
	for _, outputArtifact := range outputs {
		if outputArtifact.Type() != db_artifact.TableType {
			return nil, errors.New("Outputs of function operator must be Table Artifacts.")
		}
	}

	return &functionOperatorImpl{
		base,
	}, nil
}

func (fo *functionOperatorImpl) JobSpec() job.Spec {
	fn := fo.dbOperator.Spec.Function()
	return fo.jobSpec(fn, nil /* checkSeverity */)
}
