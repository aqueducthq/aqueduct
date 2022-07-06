import json
from typing import List

try:
    from typing import Literal
except ImportError:
    # Python 3.7 does not support typing.Literal
    from typing_extensions import Literal  # type: ignore

from aqueduct_executor.operators.utils import enums
from aqueduct_executor.operators.utils.storage import config
from pydantic import BaseModel, Extra, parse_obj_as, validator


class FunctionSpec(BaseModel):
    name: str
    type: Literal[enums.JobType.FUNCTION]
    storage_config: config.StorageConfig
    metadata_path: str
    function_path: str
    function_extract_path: str
    entry_point_file: str
    entry_point_class: str
    entry_point_method: str
    custom_args: str
    input_content_paths: List[str]
    input_metadata_paths: List[str]
    output_content_paths: List[str]
    output_metadata_paths: List[str]
    input_artifact_types: List[enums.InputArtifactType]
    output_artifact_types: List[enums.OutputArtifactType]

    # If the function produces one of these blacklisted outputs exactly, we will fail the
    # entire workflow. This is currently used to implement SEVERITY=error checks.
    blacklisted_outputs: List[str]

    class Config:
        extra = Extra.forbid

    @validator("output_artifact_types")
    def check_metric_outputs(
        cls, output_artifact_types: List[enums.OutputArtifactType]
    ) -> List[enums.OutputArtifactType]:
        if (
            len(output_artifact_types) > 1
            and enums.OutputArtifactType.FLOAT in output_artifact_types
        ):
            raise ValueError("A metric operator cannot have multiple outputs.")
        return output_artifact_types


def parse_spec(spec_json: bytes) -> FunctionSpec:
    """
    Parses a JSON string into a FunctionSpec.
    """
    data = json.loads(spec_json)

    return parse_obj_as(FunctionSpec, data)
