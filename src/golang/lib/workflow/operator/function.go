package operator

import (
	"fmt"

	"github.com/aqueducthq/aqueduct/lib/job"
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

	if len(inputs) == 0 {
		return nil, errWrongNumInputs
	}
	if len(outputs) == 0 {
		return nil, errWrongNumOutputs
	}

	return &functionOperatorImpl{
		base,
	}, nil
}

func (fo *functionOperatorImpl) JobSpec() job.Spec {
	fn := fo.dbOperator.Spec.Function()
	return fo.jobSpec(fn)
}
