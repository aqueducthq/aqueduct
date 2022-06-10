// types and enums
package operator

import (
	"database/sql/driver"
	"encoding/json"

	"github.com/aqueducthq/aqueduct/lib/collections/utils"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/check"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/function"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/metric"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/param"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/systemmetric"
	"github.com/dropbox/godropbox/errors"
)

// This file covers all operator specs.
//
// To add a new spec:
// - Add a new enum constant for `Type`
// - Add a new field in specUnion for the new spec struct
// - Implement 3 additional methods for top level Spec type:
//  - IsNewType() method to validate the type
//  - NewType() method to get the value of the type from private `spec` field
//  - NewSpecFromNewType() method to construct a spec from the new type

type Type string

const (
	FunctionType Type = "function"
	MetricType   Type = "metric"
	CheckType    Type = "check"
	ExtractType  Type = "extract"
	LoadType     Type = "load"
	ParamType    Type = "param"
	SystemMetricType Type = "systemmetric"
)

type specUnion struct {
	Type     Type               `json:"type"`
	Function *function.Function `json:"function,omitempty"`
	Check    *check.Check       `json:"check,omitempty"`
	Metric   *metric.Metric     `json:"metric,omitempty"`
	Extract  *connector.Extract `json:"extract,omitempty"`
	Load     *connector.Load    `json:"load,omitempty"`
	Param    *param.Param       `json:"param,omitempty"`
	SystemMetric    *systemmetric.SystemMetric       `json:"systemmetric,omitempty"`
}

type Spec struct {
	spec specUnion
}

func NewSpecFromFunction(f function.Function) *Spec {
	return &Spec{spec: specUnion{
		Type:     FunctionType,
		Function: &f,
	}}
}

func NewSpecFromMetric(m metric.Metric) *Spec {
	return &Spec{spec: specUnion{
		Type:   MetricType,
		Metric: &m,
	}}
}

func NewSpecFromCheck(c check.Check) *Spec {
	return &Spec{spec: specUnion{
		Type:  CheckType,
		Check: &c,
	}}
}

func NewSpecFromExtract(e connector.Extract) *Spec {
	return &Spec{spec: specUnion{
		Type:    ExtractType,
		Extract: &e,
	}}
}

func NewSpecFromLoad(l connector.Load) *Spec {
	return &Spec{spec: specUnion{
		Type: LoadType,
		Load: &l,
	}}
}

func (s Spec) Type() Type {
	return s.spec.Type
}

func (s Spec) IsFunction() bool {
	return s.Type() == FunctionType
}

func (s Spec) HasFunction() bool {
	return s.IsFunction() || s.IsCheck() || s.IsMetric()
}

func (s Spec) Function() *function.Function {
	if !s.HasFunction() {
		return nil
	}

	if s.IsFunction() {
		return s.spec.Function
	}

	if s.IsCheck() {
		return &s.Check().Function
	}

	if s.IsMetric() {
		return &s.Metric().Function
	}

	return nil
}

func (s Spec) IsMetric() bool {
	return s.Type() == MetricType
}

func (s Spec) Metric() *metric.Metric {
	if !s.IsMetric() {
		return nil
	}

	return s.spec.Metric
}

func (s Spec) IsCheck() bool {
	return s.Type() == CheckType
}

func (s Spec) Check() *check.Check {
	if !s.IsCheck() {
		return nil
	}

	return s.spec.Check
}

func (s Spec) IsExtract() bool {
	return s.Type() == ExtractType
}

func (s Spec) Extract() *connector.Extract {
	if !s.IsExtract() {
		return nil
	}

	return s.spec.Extract
}

func (s Spec) IsLoad() bool {
	return s.Type() == LoadType
}

func (s Spec) Load() *connector.Load {
	if !s.IsLoad() {
		return nil
	}

	return s.spec.Load
}

func (s Spec) IsParam() bool {
	return s.Type() == ParamType
}

func (s Spec) Param() *param.Param {
	if !s.IsParam() {
		return nil
	}

	return s.spec.Param
}

func (s Spec) IsSystemMetric() bool {
	return s.Type() == SystemMetricType
}

func (s Spec) SystemMetric() *systemmetric.SystemMetric {
	if !s.IsSystemMetric() {
		return nil
	}

	return s.spec.SystemMetric
}

func (s Spec) MarshalJSON() ([]byte, error) {
	return json.Marshal(s.spec)
}

func (s *Spec) UnmarshalJSON(rawMessage []byte) error {
	var spec specUnion
	err := json.Unmarshal(rawMessage, &spec)
	if err != nil {
		return err
	}

	// Overwrite the spec type based on the data.
	var typeCount int
	if spec.Function != nil {
		spec.Type = FunctionType
		typeCount++
	} else if spec.Metric != nil {
		spec.Type = MetricType
		typeCount++
	} else if spec.Check != nil {
		spec.Type = CheckType
		typeCount++
	} else if spec.Load != nil {
		spec.Type = LoadType
		typeCount++
	} else if spec.Extract != nil {
		spec.Type = ExtractType
		typeCount++
	} else if spec.Param != nil {
		spec.Type = ParamType
		typeCount++
	} else if spec.SystemMetric != nil {
		spec.Type = SystemMetricType
		typeCount++
	}

	if typeCount != 1 {
		return errors.Newf("Operator Spec can only be of one type. Number of types: %d", typeCount)
	}

	s.spec = spec
	return nil
}

func (s *Spec) Value() (driver.Value, error) {
	return utils.ValueJsonB(*s)
}

func (s *Spec) Scan(value interface{}) error {
	return utils.ScanJsonB(value, s)
}
