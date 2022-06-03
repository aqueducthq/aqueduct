import json
import uuid
from typing import Dict, Literal, Union

from aqueduct_executor.operators.connectors.tabular import spec as conn_spec
from aqueduct_executor.operators.function_executor import spec as func_spec
from aqueduct_executor.operators.param_executor import spec as param_spec
from aqueduct_executor.operators.utils import enums
from aqueduct_executor.operators.utils.storage import config
from pydantic import BaseModel, parse_obj_as

OperatorSpec = Union[
    conn_spec.ExtractSpec, conn_spec.LoadSpec, func_spec.FunctionSpec, param_spec.ParamSpec
]


class CompileAirflowSpec(BaseModel):
    name: str
    type: Literal[enums.JobType.COMPILE_AIRFLOW]
    storage_config: config.StorageConfig
    metadata_path: str
    output_content_path: str
    workflow_id: uuid.UUID
    workflow_name: str
    edges: Dict[uuid.UUID, uuid.UUID]


def parse_spec(spec_json: str) -> CompileAirflowSpec:
    """
    Parses a JSON string into a CompileAirflowSpec.
    """
    data = json.loads(spec_json)

    return parse_obj_as(CompileAirflowSpec, data)
    