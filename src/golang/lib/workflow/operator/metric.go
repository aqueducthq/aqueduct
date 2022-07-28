package operator

import (
	"github.com/aqueducthq/aqueduct/lib/job"
)

type metricOperatorImpl struct {
	baseFunctionOperator
}

func newMetricOperator(base baseFunctionOperator) (Operator, error) {
	base.jobName = generateFunctionJobName()

	inputs := base.inputs
	outputs := base.outputs
	if len(inputs) == 0 {
		return nil, errWrongNumInputs
	}
	if len(outputs) != 1 {
		return nil, errWrongNumOutputs
	}

	return &metricOperatorImpl{
		base,
	}, nil
}

func (mo *metricOperatorImpl) JobSpec() job.Spec {
	fn := mo.dbOperator.Spec.Metric().Function
	return mo.jobSpec(&fn)
}
