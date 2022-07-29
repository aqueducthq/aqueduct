import uuid
from typing import List

from aqueduct.artifact import Artifact, ArtifactSpec
from aqueduct.dag import DAG, Metadata
from aqueduct.enums import (
    CheckSeverity,
    FunctionGranularity,
    FunctionType,
    LoadUpdateMode,
    OperatorType,
    ServiceType,
)
from aqueduct.operators import (
    CheckSpec,
    ExtractSpec,
    FunctionSpec,
    LoadSpec,
    MetricSpec,
    Operator,
    OperatorSpec,
    RelationalDBExtractParams,
    RelationalDBLoadParams,
)
from aqueduct.table_artifact import TableArtifact
from aqueduct.utils import generate_uuid


def generate_uuids(num: int) -> List[uuid.UUID]:
    return [generate_uuid() for _ in range(num)]


def _construct_dag(
    operators: List[Operator],
    artifacts: List[Artifact],
):
    return DAG(
        operators={**{str(op.id): op for op in operators}},
        operator_by_name={**{op.name: op for op in operators}},
        artifacts={**{str(artifact.id): artifact for artifact in artifacts}},
        metadata=Metadata(),
    )


def _construct_operator(
    id: uuid.UUID,
    name: str,
    operator_type: OperatorType,
    inputs: List[uuid.UUID],
    outputs: List[uuid.UUID],
):
    """Only sets the fields needed to figure out the DAG structure, not to actually execute the operator."""
    if operator_type == OperatorType.EXTRACT:
        spec = default_extract_spec()
    elif operator_type == OperatorType.FUNCTION:
        spec = default_function_spec()
    elif operator_type == OperatorType.CHECK:
        spec = default_check_spec()
    elif operator_type == OperatorType.METRIC:
        spec = default_metric_spec()
    else:
        spec = default_load_spec()

    return Operator(
        id=id,
        name=name,
        description="",
        spec=spec,
        inputs=inputs,
        outputs=outputs,
    )


def default_extract_spec() -> OperatorSpec:
    return OperatorSpec(
        extract=ExtractSpec(
            service=ServiceType.POSTGRES,
            integration_id=generate_uuid(),
            parameters=RelationalDBExtractParams(query="This is a SQL Query"),
        )
    )


def default_function_spec() -> OperatorSpec:
    return OperatorSpec(
        function=FunctionSpec(
            type=FunctionType.FILE,
            granularity=FunctionGranularity.TABLE,
        )
    )


def default_check_spec() -> OperatorSpec:
    return OperatorSpec(
        check=CheckSpec(
            level=CheckSeverity.WARNING,
            function=FunctionSpec(
                type=FunctionType.FILE,
                granularity=FunctionGranularity.TABLE,
            ),
        )
    )


def default_metric_spec() -> OperatorSpec:
    return OperatorSpec(
        metric=MetricSpec(
            function=FunctionSpec(
                type=FunctionType.FILE,
                granularity=FunctionGranularity.TABLE,
            ),
        )
    )


def default_load_spec() -> OperatorSpec:
    return OperatorSpec(
        load=LoadSpec(
            service=ServiceType.POSTGRES,
            integration_id=generate_uuid(),
            parameters=RelationalDBLoadParams(table="output", update_mode=LoadUpdateMode.REPLACE),
        )
    )


def default_artifact(id: uuid.UUID, name: str) -> Artifact:
    return Artifact(id=id, name=name, spec=ArtifactSpec(table={}))


def default_table_artifact(
    operator_name="extract_operator",
    operator_id=None,
    artifact_name="table_artifact",
    artifact_id=None,
) -> TableArtifact:
    if not operator_id:
        operator_id = generate_uuid()
    if not artifact_id:
        artifact_id = generate_uuid()
    artifact = Artifact(id=artifact_id, name=artifact_name, spec=ArtifactSpec(table={}))
    op = _construct_operator(
        id=operator_id,
        name=operator_name,
        operator_type=OperatorType.EXTRACT,
        inputs=[],
        outputs=[artifact_id],
    )
    dag = _construct_dag(
        operators=[op],
        artifacts=[artifact],
    )
    return TableArtifact(dag=dag, artifact_id=artifact_id)
