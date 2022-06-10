import json
from pydantic import BaseModel, parse_obj_as
from typing import List


try:
    from typing import Literal
except ImportError:
    # Python 3.7 does not support typing.Literal
    from typing_extensions import Literal

from aqueduct_executor.operators.utils import enums
from aqueduct_executor.operators.utils.storage import config


class SystemMetricSpec(BaseModel):
    name: str
    type: Literal[enums.JobType.SYSTEMMETRIC]
    storage_config: config.StorageConfig
    metadata_path: str
    metricname: str
    input_content_paths: List[str]
    input_metadata_paths: List[str]
    output_content_paths: List[str]
    output_metadata_paths: List[str]
    output_artifact_types: List[enums.OutputArtifactType]


def parse_spec(spec_json: str) -> SystemMetricSpec:
    """
    Parses a JSON string into a FunctionSpec.
    """
    data = json.loads(spec_json)
    return parse_obj_as(SystemMetricSpec, data)
