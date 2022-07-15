import sys

from aqueduct_executor.operators.param_executor.spec import ParamSpec
from aqueduct_executor.operators.utils import enums, utils
from aqueduct_executor.operators.utils.execution import (
    TIP_UNKNOWN_ERROR,
    Error,
    ExecutionState,
    Logs,
    exception_traceback,
)
from aqueduct_executor.operators.utils.storage.parse import parse_storage


def run(spec: ParamSpec) -> None:
    """
    Executes a parameter operator by storing the parameter value in the output content path.
    """
    print("Job Spec: \n{}".format(spec.json()))

    storage = parse_storage(spec.storage_config)
    exec_state = ExecutionState(user_logs=Logs())
    try:
        utils.write_artifact(
            storage,
            enums.OutputArtifactType.JSON,
            spec.output_content_path,
            spec.output_metadata_path,
            spec.val,
            system_metadata={},
        )
        exec_state.status = enums.ExecutionStatus.SUCCEEDED
        utils.write_exec_state(storage, spec.metadata_path, exec_state)
    except Exception as e:
        exec_state.status = enums.ExecutionStatus.FAILED
        exec_state.failure_type = enums.FailureType.SYSTEM
        exec_state.error = Error(context=exception_traceback(e), tip=TIP_UNKNOWN_ERROR)
        print(f"Failed with system error. Full Logs:\n{exec_state.json()}")
        utils.write_exec_state(storage, spec.metadata_path, exec_state)
        sys.exit(1)
