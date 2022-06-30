import argparse
import base64
import importlib
import json
import os
import sys
import tracemalloc
from typing import Any, Callable, Dict, List, Tuple

from aqueduct_executor.operators.function_executor import spec
from aqueduct_executor.operators.function_executor.utils import OP_DIR
from aqueduct_executor.operators.utils import utils
from aqueduct_executor.operators.utils.enums import ExecutionStatus, FailureType
from aqueduct_executor.operators.utils.logging import (
    Error,
    ExecutionState,
    Logs,
    exception_traceback,
    TIP_OP_EXECUTION,
    TIP_UNKNOWN_ERROR,
)
from aqueduct_executor.operators.utils.storage.parse import parse_storage
from aqueduct_executor.operators.utils.timer import Timer

from pandas import DataFrame


def _get_py_import_path(spec: spec.FunctionSpec) -> str:
    """
    Generates the import path based on fixed function dir and
    FUNCTION_ENTRY_POINT_FILE env var.

    It removes .py (if any) from the entry point and replaces all
    '/' with '.'

    For example, entry point 'model/churn.py'  will finally become
    'app.function.model.churn', where we can import from.
    """
    file_path = spec.entry_point_file
    if file_path.endswith(".py"):
        file_path = file_path[:-3]

    if file_path.startswith("/"):
        file_path = file_path[1:]
    return ".".join([OP_DIR, file_path.replace("/", ".")])


def _import_invoke_method(spec: spec.FunctionSpec) -> Callable[..., DataFrame]:
    fn_path = spec.function_extract_path
    os.chdir(os.path.join(fn_path, OP_DIR))
    sys.path.append(fn_path)
    import_path = _get_py_import_path(spec)
    class_name = spec.entry_point_class
    method_name = spec.entry_point_method
    custom_args_str = spec.custom_args
    # Invoke the function and parse out the result object.
    module = importlib.import_module(import_path)
    if not class_name:
        return getattr(module, method_name)

    fn_class = getattr(module, class_name)
    function = fn_class()
    # Set the custom arguments if provided
    if custom_args_str:
        custom_args = json.loads(custom_args_str)
        function.set_args(custom_args)

    return getattr(function, method_name)


def _execute_function(
    spec: spec.FunctionSpec,
    inputs: List[Any],
    exec_logs: ExecutionState,
) -> Tuple[Any, Dict[str, str]]:
    """
    Invokes the given function on the input data. Does not raise an exception on any
    user function errors. Instead, returns the error message as a string.

    :param inputs: the input data to feed into the user's function.
    """

    invoke = _import_invoke_method(spec)
    timer = Timer()
    print("Invoking the function...")
    timer.start()
    tracemalloc.start()

    @exec_logs.user_fn_redirected(failure_tip=TIP_OP_EXECUTION)
    def _invoke() -> Any:
        return invoke(*inputs)

    result = _invoke()

    elapsedTime = timer.stop()
    _, peak = tracemalloc.get_traced_memory()
    system_metadata = {
        utils._RUNTIME_SEC_METRIC_NAME: str(elapsedTime),
        utils._MAX_MEMORY_MB_METRIC_NAME: str(peak / 10**6),
    }

    sys.path.pop(0)
    return result, system_metadata


def run(spec: spec.FunctionSpec) -> None:
    """
    Executes a function operator.
    """

    exec_logs = ExecutionState(user_logs=Logs())
    storage = parse_storage(spec.storage_config)
    try:
        # Read the input data from intermediate storage.
        inputs = utils.read_artifacts(
            storage, spec.input_content_paths, spec.input_metadata_paths, spec.input_artifact_types
        )

        print("Invoking the function...")
        results, system_metadata = _execute_function(spec, inputs, exec_logs)
        if exec_logs.code == ExecutionStatus.FAILED:
            # user failure
            utils.write_logs(storage, spec.metadata_path, exec_logs)
            sys.exit(1)

        print("Function invoked successfully!")
        # Force all results to be of type `list`, so we can always loop over them.
        if not isinstance(results, list):
            results = [results]

        utils.write_artifacts(
            storage,
            spec.output_artifact_types,
            spec.output_content_paths,
            spec.output_metadata_paths,
            results,
            system_metadata=system_metadata,
        )

        exec_logs.code = ExecutionStatus.SUCCEEDED
        utils.write_logs(storage, spec.metadata_path, exec_logs)
        print(f"Succeeded! Full logs: {exec_logs.json()}")

    except Exception as e:
        exec_logs.code = ExecutionStatus.FAILED
        exec_logs.failure_type = FailureType.SYSTEM
        exec_logs.error = Error(
            context=exception_traceback(e),
            tip=TIP_UNKNOWN_ERROR,
        )
        print(f"Failed with system error. Full Logs:\n{exec_logs.json()}")
        utils.write_logs(storage, spec.metadata_path, exec_logs)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--spec", required=True)
    args = parser.parse_args()

    spec_json = base64.b64decode(args.spec)
    spec = spec.parse_spec(spec_json)

    print("Started %s job: %s" % (spec.type, spec.name))

    run(spec)
