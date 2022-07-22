import json
from typing import Dict, List, Literal, Union

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
    dag_id: str
    cron_schedule: str
    task_specs: Dict[str, OperatorSpec]
    task_edges: Dict[str, List[str]]


def parse_spec(spec_json: bytes) -> CompileAirflowSpec:
    """
    Parses a JSON string into a CompileAirflowSpec.
    """
    data = json.loads(spec_json)

    return parse_obj_as(CompileAirflowSpec, data)
