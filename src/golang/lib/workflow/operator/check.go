package operator

import (
	"encoding/json"

	"github.com/aqueducthq/aqueduct/lib/collections/operator/check"
	"github.com/aqueducthq/aqueduct/lib/job"
	log "github.com/sirupsen/logrus"
)

type checkOperatorImpl struct {
	baseFunctionOperator
}

func newCheckOperator(base baseFunctionOperator) (Operator, error) {
	base.jobName = generateFunctionJobName()

	inputs := base.inputs
	outputs := base.outputs
	if len(inputs) == 0 {
		return nil, errWrongNumInputs
	}
	if len(outputs) != 1 {
		return nil, errWrongNumOutputs
	}

	return &checkOperatorImpl{
		base,
	}, nil
}

func (co *checkOperatorImpl) hasErrorSeverity() bool {
	return co.dbOperator.Spec.Check().Level == check.ErrorLevel
}

func (co *checkOperatorImpl) JobSpec() job.Spec {
	fn := co.dbOperator.Spec.Check().Function
	spec := co.jobSpec(&fn)

	// This will tell the orchestration engine to fail the workflow
	// if the check fails with sufficient severity.
	if co.hasErrorSeverity() {
		falseSerialized, err := json.Marshal(false)
		if err != nil {
			log.Errorf("Internal error: Operator %s is unable to marshal `false`", co.Name())
		}

		fnSpec := spec.(*job.FunctionSpec)
		fnSpec.BlacklistedOutputs = append(fnSpec.BlacklistedOutputs, string(falseSerialized))
		return fnSpec
	}
	return spec
}
