package artifact

import (
	"database/sql/driver"

	"github.com/aqueducthq/aqueduct/lib/collections/utils"
)

// This file covers all artifact specs.
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
	Untyped       Type = "untyped"
	StringType    Type = "string"
	BoolType      Type = "bool"
	NumericType   Type = "numeric"
	DictType      Type = "dictionary"
	TupleType     Type = "tuple"
	TabularType   Type = "tabular"
	JsonType      Type = "json"
	BytesType     Type = "bytes"
	ImageType     Type = "image"
	PicklableType Type = "picklable"
)

type Spec struct {
	Type Type `json:"type"`
}

func (s *Spec) Value() (driver.Value, error) {
	return utils.ValueJsonB(*s)
}

func (s *Spec) Scan(value interface{}) error {
	return utils.ScanJsonB(value, s)
}
