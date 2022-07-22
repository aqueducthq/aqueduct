import textwrap
import uuid
from typing import Dict, List, Optional

from aqueduct.artifact import Artifact
from aqueduct.dag import Metadata
from aqueduct.enums import ExecutionStatus, FailureType
from aqueduct.operators import Operator
from aqueduct.utils import human_readable_timestamp
from pydantic import BaseModel


class Logs(BaseModel):
    stdout: str = ""
    stderr: str = ""

    def is_empty(self) -> bool:
        return self.stdout == "" and self.stderr == ""

    def __str__(self) -> str:
        return textwrap.dedent(
            f"""stdout:
            {self.stdout}
            --------------------------
            stderr:
            {self.stderr}""",
        )


class Error(BaseModel):
    context: str = ""
    tip: str = ""


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

    user_logs: Optional[Logs] = None
    error: Optional[Error] = None
    status: ExecutionStatus = ExecutionStatus.UNKNOWN
    failure_type: Optional[FailureType] = None


class PreviewResponse(BaseModel):
    """This is the response object returned by api_client.preview().

    Attributes:
        status:
            The execution state of preview.
        operator_results:
            A map from an operator id to its OperatorResult object.
            All operators that were run will appear in this map.

        artifact_results:
            A map from an artifact id to its base64 encoded string.
            Artifact results will only appear in this map if explicitly
            specified in the `target_ids` on the request.
    """

    status: ExecutionStatus
    operator_results: Dict[uuid.UUID, OperatorResult]
    artifact_results: Dict[uuid.UUID, str]


class RegisterWorkflowResponse(BaseModel):
    """This is the response object returned by api_client.register_workflow().

    Attributes:
        id:
            The uuid if of the newly registered workflow.
    """

    id: uuid.UUID


class ListWorkflowResponseEntry(BaseModel):
    """A list of these response objects is returned by api_client.list_workflows()
    and corresponds with a single workflow.

    Attributes:
        id, name, description:
            The id, name, and description of the workflow.
        created_at:
            The unix timestamp in seconds that the workflow was first created at.
        last_run_at:
            The unit timestamp in seconds that the last workflow run was started.
        status:
            The execution status of the latest run of this workflow.
    """

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
    """Represents a dag structure that could have been executed multiple times.

    It is an essentially a "version" of a flow.

    Attributes:
        id:
            The id of the workflow dag. This is not useful to the user.
        workflow_id:
            The id of the workflow that this dag belongs to.
        metadata:
            This workflow version's metadata like description, schedule, etc.
        operators, artifacts:
            Describes this workflow version's dag structure.

    Excluded Attributes:
        created_at, storage_config
    """

    id: uuid.UUID
    workflow_id: uuid.UUID
    metadata: Metadata
    operators: Dict[str, Operator]
    artifacts: Dict[str, Artifact]


class WorkflowDagResultResponse(BaseModel):
    """Represents the result of a single workflwo run.

    Attributes:
        id:
            The id of the workflow run. This is the same id users can use to fetch
            FlowRuns.
        created_at:
            The unix timestamp in seconds that this workflow run was started at.
        status:
            The execution status of this workflow run.
        workflow_dag_id:
            This id can be used to find the corresponding workflow dag version.
    """

    id: uuid.UUID
    created_at: int
    status: ExecutionStatus
    workflow_dag_id: uuid.UUID

    def to_readable_dict(self) -> Dict[str, str]:
        return {
            "run_id": str(self.id),
            "created_at": human_readable_timestamp(self.created_at),
            "status": self.status.value,
        }


class GetWorkflowResponse(BaseModel):
    """This is the response object returned by api_client.get_workflow().

    Attributes:
        workflow_dags:
            All the historical workflow dags.
        workflow_dag_results:
            All the historical workflow results.

    Excluded Attributes:
        watcher_auth_ids
    """

    workflow_dags: Dict[uuid.UUID, WorkflowDagResponse]
    workflow_dag_results: List[WorkflowDagResultResponse]
