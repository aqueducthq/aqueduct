from typing import List, Optional, Union
import uuid

from pydantic import BaseModel

from aqueduct.enums import (
    GoogleSheetsSaveMode,
    ServiceType,
    FunctionType,
    FunctionGranularity,
    GithubRepoConfigContentType,
    OperatorType,
    SalesforceExtractType,
    S3FileFormat,
    LoadUpdateMode,
    CheckSeverity,
)
from aqueduct.error import AqueductError
from aqueduct.integrations.integration import IntegrationInfo


class GithubMetadata(BaseModel):
    """
    Specifies a destination in github integration.
    There are two ways to specify the content:
    -   by `path`, which points to a file or dir in the github repo.
    -   from `repo_config_content_type` and `repo_config_content_name`, which points to
        information stored in the repo's `.aqconfig`.
    If using `repo_config` content, backend will ignore `path` and overwrite it with
    the `path` specified in `.aqconfig`.
    """

    owner: str
    repo: str
    branch: str
    path: Optional[str] = None
    repo_config_content_type: Optional[GithubRepoConfigContentType] = None
    repo_config_content_name: Optional[str] = None
    commit_id: Optional[str] = None


class RelationalDBExtractParams(BaseModel):
    query: Optional[str] = None
    github_metadata: Optional[GithubMetadata] = None


class SalesforceExtractParams(BaseModel):
    type: SalesforceExtractType
    query: str


class GoogleSheetsExtractParams(BaseModel):
    spreadsheet_id: str


class S3ExtractParams(BaseModel):
    filepath: str
    format: S3FileFormat


UnionExtractParams = Union[
    SalesforceExtractParams,
    S3ExtractParams,
    GoogleSheetsExtractParams,
    RelationalDBExtractParams,
]


class ExtractSpec(BaseModel):
    service: ServiceType
    integration_id: uuid.UUID
    parameters: UnionExtractParams


class RelationalDBLoadParams(BaseModel):
    table: str
    update_mode: LoadUpdateMode


class SalesforceLoadParams(BaseModel):
    object: str


class GoogleSheetsLoadParams(BaseModel):
    filepath: str
    save_mode: GoogleSheetsSaveMode


class S3LoadParams(BaseModel):
    filepath: str
    format: S3FileFormat


UnionLoadParams = Union[
    SalesforceLoadParams, S3LoadParams, GoogleSheetsLoadParams, RelationalDBLoadParams
]


# Internal class used by SDK to represent the config for loading to an integration.
class SaveConfig(BaseModel):
    integration_info: IntegrationInfo
    parameters: UnionLoadParams


# Class expected by backend for a load operator.
class LoadSpec(BaseModel):
    service: ServiceType
    integration_id: uuid.UUID
    parameters: UnionLoadParams


class EntryPoint(BaseModel):
    file: str
    class_name: Optional[str]
    method: str


class FunctionSpec(BaseModel):
    type: FunctionType
    language = "Python"
    granularity: FunctionGranularity
    s3_path: Optional[str]
    github_metadata: Optional[GithubMetadata]
    entry_point: Optional[EntryPoint] = None

    # Function zip file.
    file: Optional[bytes] = None

    class Config:
        fields = {"file": {"exclude": ...}}


class MetricSpec(BaseModel):
    function: FunctionSpec

class SystemMetricSpec(BaseModel):
    metricname: str


class CheckSpec(BaseModel):
    level: CheckSeverity
    function: FunctionSpec


class ParamSpec(BaseModel):
    val: str


class OperatorSpec(BaseModel):
    extract: Optional[ExtractSpec]
    load: Optional[LoadSpec]
    function: Optional[FunctionSpec]
    metric: Optional[MetricSpec]
    check: Optional[CheckSpec]
    param: Optional[ParamSpec]
    systemmetric: Optional[SystemMetricSpec]


class Operator(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    spec: OperatorSpec
    inputs: List[uuid.UUID] = []
    outputs: List[uuid.UUID] = []

    def file(self) -> Optional[bytes]:
        if self.spec.function:
            return self.spec.function.file
        if self.spec.metric:
            return self.spec.metric.function.file
        if self.spec.check:
            return self.spec.check.function.file

        return None


def get_operator_type(operator: Operator) -> OperatorType:
    if operator.spec.extract is not None:
        return OperatorType.EXTRACT
    if operator.spec.load is not None:
        return OperatorType.LOAD
    if operator.spec.function is not None:
        return OperatorType.FUNCTION
    if operator.spec.metric is not None:
        return OperatorType.METRIC
    if operator.spec.check is not None:
        return OperatorType.CHECK
    if operator.spec.param is not None:
        return OperatorType.PARAM
    if operator.spec.systemmetric is not None:
        return OperatorType.SYSTEMMETRIC
    else:
        raise AqueductError("Invalid operator type")
