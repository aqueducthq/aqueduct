from typing import Optional, Dict, List
import uuid
from pydantic import BaseModel

from aqueduct.artifact import Artifact
from aqueduct.dag import Metadata
from aqueduct.enums import ExecutionStatus
from aqueduct.operators import Operator
from aqueduct.utils import human_readable_timestamp


class OperatorResult(BaseModel):
    """This represents the results of a single operator run.

    Attributes:
        logs:
            The dictionary generated by this operator.
        err_msg:
            The error message if the operator fails.
            Empty if the operator ran successfully.
        test_result:
            Only set if this operator represents a unit test on an artifact.
    """

    logs: Optional[Dict[str, str]]
    err_msg: Optional[str]


class TableArtifactResult(BaseModel):
    """This represents the results of a single table artifact.

    Attributes:
        table_schema:
            A list of maps, which each map representing the name -> type
            of a single column.

        data:
            A byte string that can be deserialized into a Pandas dataframe.
    """

    table_schema: Optional[List[Dict[str, str]]]
    data: str


class MetricArtifactResult(BaseModel):
    val: float


class CheckArtifactResult(BaseModel):
    passed: bool


class ParamArtifactResult(BaseModel):
    val: str


class ArtifactResult(BaseModel):
    table: Optional[TableArtifactResult]
    metric: Optional[MetricArtifactResult]
    check: Optional[CheckArtifactResult]
    param: Optional[ParamArtifactResult]


class PreviewResponse(BaseModel):
    """This is the response object returned by api_client.preview().

    Attributes:
        status:
            The execution state of preview.
        operator_results:
            A map from an operator id to its OperatorResult object.
            All operators that were run will appear in this map.

        artifact_results:
            A map from an artifact id to its ArtifactResult object.
            ArtifactResults will only appear in this map if explicitly
            specified in the `target_ids` on the request.
    """

    status: ExecutionStatus
    operator_results: Dict[uuid.UUID, OperatorResult]
    artifact_results: Dict[uuid.UUID, ArtifactResult]


class RegisterWorkflowResponse(BaseModel):
    """The is the response object returned by api_client.register_workflow().

    Attributes:
        id:
            The uuid if of the newly registered workflow.
    """

    id: uuid.UUID


class ListWorkflowResponseEntry(BaseModel):
    """TODO: docstring"""

    id: uuid.UUID
    name: str
    description: str
    created_at: int
    last_run_at: int
    status: ExecutionStatus

    def to_readable_dict(self) -> Dict[str, str]:
        return {
            "flow_id": str(self.id),
            "name": self.name,
            "description": self.description,
            "created_at": human_readable_timestamp(self.created_at),
            "last_run_at": human_readable_timestamp(self.last_run_at),
            "last_run_status": str(self.status),
        }


class WorkflowDagResponse(BaseModel):
    # TODO: docstring (MISSING: created_at, storage_config)
    id: uuid.UUID
    workflow_id: uuid.UUID
    metadata: Metadata
    operators: Dict[str, Operator]
    artifacts: Dict[str, Artifact]


class WorkflowDagResultResponse(BaseModel):
    id: uuid.UUID
    created_at: int
    status: ExecutionStatus
    workflow_dag_id: uuid.UUID

    def to_readable_dict(self) -> Dict[str, str]:
        return {
            "run_id": str(self.id),
            "created_at": human_readable_timestamp(self.created_at),
            "status": str(self.status),
        }


class GetWorkflowResponse(BaseModel):
    # TODO: docstring (MISSING: watcher_auth_ids)
    workflow_dags: Dict[uuid.UUID, WorkflowDagResponse]
    workflow_dag_results: List[WorkflowDagResultResponse]
