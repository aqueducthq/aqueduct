package job

import (
	"bytes"
	"encoding/base64"
	"encoding/gob"
	"encoding/json"

	"github.com/aqueducthq/aqueduct/lib/collections/integration"
	"github.com/aqueducthq/aqueduct/lib/collections/operator/connector"
	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aqueducthq/aqueduct/lib/database"
	"github.com/aqueducthq/aqueduct/lib/vault"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector/auth"
	"github.com/aqueducthq/aqueduct/lib/workflow/operator/connector/github"
	"github.com/dropbox/godropbox/errors"
)

var (
	ErrInvalidJobSpec           = errors.New("Invalid job spec.")
	ErrInvalidSerializationType = errors.New("Invalid serialization type.")
)

type JobType string

const (
	WorkflowRetentionName = "workflowretentionjob"
)

type SerializationType string

const (
	JsonSerializationType SerializationType = "json"
	GobSerializationType  SerializationType = "gob"
)

const (
	WorkflowJobType       JobType = "workflow"
	FunctionJobType       JobType = "function"
	ParamJobType          JobType = "param"
	SystemMetricJobType   JobType = "system_metric"
	AuthenticateJobType   JobType = "authenticate"
	ExtractJobType        JobType = "extract"
	LoadJobType           JobType = "load"
	LoadTableJobType      JobType = "load-table"
	DiscoverJobType       JobType = "discover"
	WorkflowRetentionType JobType = "workflow_retention"
)

// `ExecutorConfiguration` represents the configuration variables that are
// used by the Executor cron job responsible for executing transformations
// on datasets.
type ExecutorConfiguration struct {
	Database   *database.DatabaseConfig `yaml:"metadata" json:"metadata"`
	Vault      vault.Config             `yaml:"vault" json:"vault"`
	JobManager Config                   `yaml:"jobManager" json:"job_manager"`
}

type Spec interface {
	Type() JobType
	JobName() string
}

// BaseSpec defines fields shared by all job specs.
type BaseSpec struct {
	Type JobType `json:"type"  yaml:"type"`
	Name string  `json:"name"  yaml:"name"`
}

func (bs *BaseSpec) JobName() string {
	return bs.Name
}

type WorkflowRetentionSpec struct {
	BaseSpec
	ExecutorConfig *ExecutorConfiguration
}

type WorkflowSpec struct {
	BaseSpec
	WorkflowId     string               `json:"workflow_id" yaml:"workflowId"`
	GithubManager  github.ManagerConfig `json:"github_manager" yaml:"github_manager"`
	Parameters     map[string]string    `json:"parameters" yaml:"parameters"`
	ExecutorConfig *ExecutorConfiguration
}

// BasePythonSpec defines fields shared by all Python job specs.
// These Python jobs can be one-off jobs (e.g. Authenticate, Discover)
// or Workflow operators (e.g. Function, Extract, Load).
type BasePythonSpec struct {
	BaseSpec
	StorageConfig shared.StorageConfig `json:"storage_config"  yaml:"storage_config"`
	MetadataPath  string               `json:"metadata_path"  yaml:"metadata_path"`
}

type FunctionSpec struct {
	BasePythonSpec
	FunctionPath        string   `json:"function_path"  yaml:"function_path"`
	FunctionExtractPath string   `json:"function_extract_path" yaml:"function_extract_path"`
	EntryPointFile      string   `json:"entry_point_file"  yaml:"entry_point_file"`
	EntryPointClass     string   `json:"entry_point_class"  yaml:"entry_point_class"`
	EntryPointMethod    string   `json:"entry_point_method"  yaml:"entry_point_method"`
	CustomArgs          string   `json:"custom_args"  yaml:"custom_args"`
	InputContentPaths   []string `json:"input_content_paths"  yaml:"input_content_paths"`
	InputMetadataPaths  []string `json:"input_metadata_paths"  yaml:"input_metadata_paths"`
	OutputContentPaths  []string `json:"output_content_paths"  yaml:"output_content_paths"`
	OutputMetadataPaths []string `json:"output_metadata_paths"  yaml:"output_metadata_paths"`

	// If the function outputs a value that exists in this list, we will fail the entire workflow.
	// This list contains the json-serialized version of the offending values.
	// Must be set to nil if there are no blacklisted outputs expected.
	BlacklistedOutputs []string `json:"blacklisted_outputs" yaml:"blacklisted_outputs"`
}

type ParamSpec struct {
	BasePythonSpec
	Val                string `json:"val"  yaml:"val"`
	OutputContentPath  string `json:"output_content_path"  yaml:"output_content_path"`
	OutputMetadataPath string `json:"output_metadata_path"  yaml:"output_metadata_path"`
}

type SystemMetricSpec struct {
	BasePythonSpec
	MetricName         string   `json:"metric_name"  yaml:"metric_name"`
	InputMetadataPaths []string `json:"input_metadata_paths"  yaml:"input_metadata_paths"`
	OutputContentPath  string   `json:"output_content_path"  yaml:"output_content_path"`
	OutputMetadataPath string   `json:"output_metadata_path"  yaml:"output_metadata_path"`
}

type ExtractSpec struct {
	BasePythonSpec
	ConnectorName   integration.Service     `json:"connector_name"  yaml:"connector_name"`
	ConnectorConfig auth.Config             `json:"connector_config"  yaml:"connector_config"`
	Parameters      connector.ExtractParams `json:"parameters"  yaml:"parameters"`

	// These input fields are only used to record user-defined parameters for relational queries.
	InputParamNames    []string `json:"input_param_names" yaml:"input_param_names"`
	InputContentPaths  []string `json:"input_content_paths" yaml:"input_content_paths"`
	InputMetadataPaths []string `json:"input_metadata_paths" yaml:"input_metadata_paths"`
	OutputContentPath  string   `json:"output_content_path"  yaml:"output_content_path"`
	OutputMetadataPath string   `json:"output_metadata_path"  yaml:"output_metadata_path"`
}

type LoadSpec struct {
	BasePythonSpec
	ConnectorName     integration.Service  `json:"connector_name"  yaml:"connector_name"`
	ConnectorConfig   auth.Config          `json:"connector_config"  yaml:"connector_config"`
	Parameters        connector.LoadParams `json:"parameters"  yaml:"parameters"`
	InputContentPath  string               `json:"input_content_path"  yaml:"input_content_path"`
	InputMetadataPath string               `json:"input_metadata_path"  yaml:"input_metadata_path"`
}

type LoadTableSpec struct {
	BasePythonSpec
	ConnectorName   integration.Service `json:"connector_name"  yaml:"connector_name"`
	ConnectorConfig auth.Config         `json:"connector_config"  yaml:"connector_config"`
	CSV             string              `json:"csv"  yaml:"csv"`
	LoadParameters  LoadSpec            `json:"load_parameters"  yaml:"load_parameters"`
}

type AuthenticateSpec struct {
	BasePythonSpec
	ConnectorName   integration.Service `json:"connector_name"  yaml:"connector_name"`
	ConnectorConfig auth.Config         `json:"connector_config"  yaml:"connector_config"`
}

type DiscoverSpec struct {
	BasePythonSpec
	ConnectorName     integration.Service `json:"connector_name"  yaml:"connector_name"`
	ConnectorConfig   auth.Config         `json:"connector_config"  yaml:"connector_config"`
	OutputContentPath string              `json:"output_content_path"  yaml:"output_content_path"`
}

func (*WorkflowRetentionSpec) Type() JobType {
	return WorkflowRetentionType
}

func (*WorkflowSpec) Type() JobType {
	return WorkflowJobType
}

func (*FunctionSpec) Type() JobType {
	return FunctionJobType
}

func (*ParamSpec) Type() JobType {
	return ParamJobType
}

func (*AuthenticateSpec) Type() JobType {
	return AuthenticateJobType
}

func (*SystemMetricSpec) Type() JobType {
	return SystemMetricJobType
}

func (*ExtractSpec) Type() JobType {
	return ExtractJobType
}

func (*LoadSpec) Type() JobType {
	return LoadJobType
}

func (*LoadTableSpec) Type() JobType {
	return LoadTableJobType
}

func (*DiscoverSpec) Type() JobType {
	return DiscoverJobType
}

// NewWorkflowRetentionSpec constructs a Spec for a WorkflowRetentionJob.
func NewWorkflowRetentionJobSpec(
	database *database.DatabaseConfig,
	vault vault.Config,
	jobManager Config,
) Spec {
	return &WorkflowRetentionSpec{
		BaseSpec: BaseSpec{
			Type: WorkflowRetentionType,
			Name: WorkflowRetentionName,
		},

		ExecutorConfig: &ExecutorConfiguration{
			Database:   database,
			Vault:      vault,
			JobManager: jobManager,
		},
	}
}

// NewWorkflowSpec constructs a Spec for a WorkflowJob.
func NewWorkflowSpec(
	name string,
	workflowId string,
	database *database.DatabaseConfig,
	vault vault.Config,
	jobManager Config,
	githubManager github.ManagerConfig,
	parameters map[string]string,
) Spec {
	return &WorkflowSpec{
		BaseSpec: BaseSpec{
			Type: WorkflowJobType,
			Name: name,
		},
		WorkflowId:    workflowId,
		GithubManager: githubManager,
		Parameters:    parameters,
		ExecutorConfig: &ExecutorConfiguration{
			Database:   database,
			Vault:      vault,
			JobManager: jobManager,
		},
	}
}

func NewBasePythonSpec(
	jobType JobType,
	name string,
	storageConfig shared.StorageConfig,
	metadataPath string,
) BasePythonSpec {
	return BasePythonSpec{
		BaseSpec: BaseSpec{
			Type: jobType,
			Name: name,
		},
		StorageConfig: storageConfig,
		MetadataPath:  metadataPath,
	}
}

func NewAuthenticateSpec(
	name string,
	storageConfig *shared.StorageConfig,
	metadataPath string,
	connectorName integration.Service,
	connectorConfig auth.Config,
) Spec {
	return &AuthenticateSpec{
		BasePythonSpec: BasePythonSpec{
			BaseSpec: BaseSpec{
				Type: AuthenticateJobType,
				Name: name,
			},
			StorageConfig: *storageConfig,
			MetadataPath:  metadataPath,
		},
		ConnectorName:   connectorName,
		ConnectorConfig: connectorConfig,
	}
}

// NewExtractSpec constructs a Spec for an ExtractJob.
func NewExtractSpec(
	name string,
	storageConfig *shared.StorageConfig,
	metadataPath string,
	connectorName integration.Service,
	connectorConfig auth.Config,
	parameters connector.ExtractParams,
	inputParamNames []string,
	inputContentPaths []string,
	inputMetadataPaths []string,
	outputContentPath string,
	outputMetadataPath string,
) Spec {
	return &ExtractSpec{
		BasePythonSpec: BasePythonSpec{
			BaseSpec: BaseSpec{
				Type: ExtractJobType,
				Name: name,
			},
			StorageConfig: *storageConfig,
			MetadataPath:  metadataPath,
		},
		InputParamNames:    inputParamNames,
		InputContentPaths:  inputContentPaths,
		InputMetadataPaths: inputMetadataPaths,
		ConnectorName:      connectorName,
		ConnectorConfig:    connectorConfig,
		Parameters:         parameters,
		OutputContentPath:  outputContentPath,
		OutputMetadataPath: outputMetadataPath,
	}
}

// NewLoadTableSpec constructs a Spec for a LoadTableJob.
func NewLoadTableSpec(
	name string,
	csv string,
	storageConfig *shared.StorageConfig,
	metadataPath string,
	connectorName integration.Service,
	connectorConfig auth.Config,
	parameters connector.LoadParams,
	inputContentPath string,
	inputMetadataPath string,
) Spec {
	return &LoadTableSpec{
		BasePythonSpec: BasePythonSpec{
			BaseSpec: BaseSpec{
				Type: LoadTableJobType,
				Name: name,
			},
			StorageConfig: *storageConfig,
			MetadataPath:  metadataPath,
		},
		ConnectorName:   connectorName,
		ConnectorConfig: connectorConfig,
		CSV:             csv,
		LoadParameters: LoadSpec{
			BasePythonSpec: BasePythonSpec{
				BaseSpec: BaseSpec{
					Type: LoadJobType,
					Name: name,
				},
				StorageConfig: *storageConfig,
				MetadataPath:  metadataPath,
			},
			ConnectorName:     connectorName,
			ConnectorConfig:   connectorConfig,
			Parameters:        parameters,
			InputContentPath:  inputContentPath,
			InputMetadataPath: inputMetadataPath,
		},
	}
}

// NewDiscoverSpec constructs a Spec for a DiscoverJob.
func NewDiscoverSpec(
	name string,
	storageConfig *shared.StorageConfig,
	metadataPath string,
	connectorName integration.Service,
	connectorConfig auth.Config,
	outputContentPath string,
) Spec {
	return &DiscoverSpec{
		BasePythonSpec: BasePythonSpec{
			BaseSpec: BaseSpec{
				Type: DiscoverJobType,
				Name: name,
			},
			StorageConfig: *storageConfig,
			MetadataPath:  metadataPath,
		},
		ConnectorName:     connectorName,
		ConnectorConfig:   connectorConfig,
		OutputContentPath: outputContentPath,
	}
}

// `EncodeSpec` first serialize `spec` according to `SerializationType` and returns the base64 encoded string.
// The encoded string can be safely passed around without any escaping issue (e.g. as envVar)
func EncodeSpec(spec Spec, serializationType SerializationType) (string, error) {
	var specData []byte
	var err error
	if serializationType == JsonSerializationType {
		specData, err = json.Marshal(spec)
		if err != nil {
			return "", err
		}
		return base64.StdEncoding.EncodeToString(specData), nil
	} else if serializationType == GobSerializationType {
		var buf bytes.Buffer
		encoder := gob.NewEncoder(&buf)
		if err := encoder.Encode(&spec); err != nil {
			return "", err
		}

		return base64.StdEncoding.EncodeToString(buf.Bytes()), nil
	}

	return "", ErrInvalidSerializationType
}

func DecodeSpec(specData string, serializationType SerializationType) (Spec, error) {
	specBytes, err := base64.StdEncoding.DecodeString(specData)
	if err != nil {
		return nil, err
	}

	var spec Spec
	if serializationType == JsonSerializationType {
		var base BaseSpec
		if err := json.Unmarshal(specBytes, &base); err != nil {
			return nil, err
		}

		switch base.Type {
		case WorkflowJobType:
			spec = &WorkflowSpec{}
		case WorkflowRetentionType:
			spec = &WorkflowRetentionSpec{}
		case FunctionJobType:
			spec = &FunctionSpec{}
		case AuthenticateJobType:
			spec = &AuthenticateSpec{}
		case ExtractJobType:
			spec = &ExtractSpec{}
		case LoadJobType:
			spec = &LoadSpec{}
		case LoadTableJobType:
			spec = &LoadTableSpec{}
		case DiscoverJobType:
			spec = &DiscoverSpec{}
		default:
			return nil, errors.Newf("Unknown job type: %v", base.Type)
		}

		if err := json.Unmarshal(specBytes, spec); err != nil {
			return nil, err
		}

		return spec, nil
	} else if serializationType == GobSerializationType {
		buf := bytes.NewBuffer(specBytes)
		decoder := gob.NewDecoder(buf)
		if err := decoder.Decode(&spec); err != nil {
			return nil, err
		}

		return spec, nil
	}

	return nil, ErrInvalidSerializationType
}
