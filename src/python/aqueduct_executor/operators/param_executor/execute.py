import traceback
import sys

from aqueduct_executor.operators.utils import enums, utils
from aqueduct_executor.operators.param_executor import spec
from aqueduct_executor.operators.utils.storage.parse import parse_storage


def run(spec: spec.ParamSpec) -> None:
    """
    Executes a parameter operator by storing the parameter value in the output content path.
    """
    storage = parse_storage(spec.storage_config)
    try:
        utils.write_artifact(
            storage,
            spec.output_content_path,
            spec.output_metadata_path,
            spec.val,
            {},
            enums.OutputArtifactType.JSON,
        )
        utils.write_operator_metadata(storage, spec.metadata_path, "", {})
    except Exception as e:
        utils.write_operator_metadata(storage, spec.metadata_path, str(e), {})
        print("Exception Raised: ", e)
        traceback.print_tb(e.__traceback__)
        sys.exit(1)
