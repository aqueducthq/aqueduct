import sys

from aqueduct_executor.operators.system_metric_executor.spec import SystemMetricSpec
from aqueduct_executor.operators.utils import enums, utils
from aqueduct_executor.operators.utils.execution import (
    TIP_UNKNOWN_ERROR,
    Error,
    ExecutionState,
    Logs,
    exception_traceback,
)
from aqueduct_executor.operators.utils.storage.parse import parse_storage


def run(spec: SystemMetricSpec) -> None:
    """
    Executes a system metric operator by storing the requested system metrics value in the output content path.
    """
    print("Job Spec: \n{}".format(spec.json()))

    storage = parse_storage(spec.storage_config)
    exec_state = ExecutionState(user_logs=Logs())
    try:
        # We currently allow the spec to contain multiple input_metadata paths.
        # A system metric currently spans over a single operator.
        # The scheduler enforces this requirement before the executor is run.
        system_metadata = utils.read_system_metadata(storage, spec.input_metadata_paths)
        utils.write_artifact(
            storage,
            enums.OutputArtifactType.FLOAT,
            spec.output_content_path,
            spec.output_metadata_path,
            float(system_metadata[0][spec.metric_name]),
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
