import importlib
import json
import os
import sys
import tracemalloc
from typing import Any, Callable, Dict, List, Tuple

from PIL import Image
import numpy as np
import cloudpickle as pickle

from aqueduct_executor.operators.function_executor.spec import FunctionSpec
from aqueduct_executor.operators.function_executor.spec import FunctionSpec
from aqueduct_executor.operators.function_executor.utils import OP_DIR
from aqueduct_executor.operators.utils import utils
from aqueduct_executor.operators.utils.enums import ExecutionStatus, FailureType, ArtifactType
from aqueduct_executor.operators.utils.execution import (
    TIP_BLACKLISTED_OUTPUT,
    TIP_OP_EXECUTION,
    TIP_UNKNOWN_ERROR,
    Error,
    ExecutionState,
    Logs,
    exception_traceback,
)
from aqueduct_executor.operators.utils.storage.parse import parse_storage
from aqueduct_executor.operators.utils.timer import Timer
from pandas import DataFrame


def _get_py_import_path(spec: FunctionSpec) -> str:
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


def _import_invoke_method(spec: FunctionSpec) -> Callable[..., Any]:
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
        return getattr(module, method_name)  # type: ignore

    fn_class = getattr(module, class_name)
    function = fn_class()
    # Set the custom arguments if provided
    if custom_args_str:
        custom_args = json.loads(custom_args_str)
        function.set_args(custom_args)

    return getattr(function, method_name)  # type: ignore


def _infer_result_type(result: Any) -> ArtifactType:
    if isinstance(result, DataFrame):
        return ArtifactType.TABULAR
    elif isinstance(result, Image.Image):
        return ArtifactType.IMAGE
    elif isinstance(result, bytes):
        return ArtifactType.BYTES
    elif isinstance(result, str):
        # We first check if the result is a valid JSON string.
        try:
            json.loads(result)
            return ArtifactType.JSON
        except:
            return ArtifactType.STRING
    elif isinstance(result, bool) or isinstance(result, np.bool_):
        return ArtifactType.BOOL
    elif isinstance(result, int) or isinstance(result, float) or isinstance(result, np.number):
        return ArtifactType.NUMERIC
    elif isinstance(result, dict):
        return ArtifactType.DICT
    elif isinstance(result, tuple):
        return ArtifactType.TUPLE
    else:
        try:
            pickle.dumps(result)
            return ArtifactType.PICKLABLE
        except:
            raise Exception("Failed to map type %s to supported artifact type." % type(result))


def _execute_function(
    spec: FunctionSpec,
    inputs: List[Any],
    exec_state: ExecutionState,
) -> Tuple[Any, ArtifactType, Dict[str, str]]:
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

    @exec_state.user_fn_redirected(failure_tip=TIP_OP_EXECUTION)
    def _invoke() -> Any:
        return invoke(*inputs)

    result = _invoke()
    inferred_result_type = _infer_result_type(result)

    elapsedTime = timer.stop()
    _, peak = tracemalloc.get_traced_memory()
    system_metadata = {
        utils._RUNTIME_SEC_METRIC_NAME: str(elapsedTime),
        utils._MAX_MEMORY_MB_METRIC_NAME: str(peak / 10**6),
    }

    sys.path.pop(0)
    return result, inferred_result_type, system_metadata


def run(spec: FunctionSpec) -> None:
    """
    Executes a function operator.
    """
    print("Started %s job: %s" % (spec.type, spec.name))

    exec_state = ExecutionState(user_logs=Logs())
    storage = parse_storage(spec.storage_config)
    try:
        # Read the input data from intermediate storage.
        inputs, _ = utils.read_artifacts(
            storage, spec.input_content_paths, spec.input_metadata_paths
        )

        print("Invoking the function...")
        result, result_type, system_metadata = _execute_function(spec, inputs, exec_state)
        if exec_state.status == ExecutionStatus.FAILED:
            # user failure
            utils.write_exec_state(storage, spec.metadata_path, exec_state)
            sys.exit(1)

        print("Function invoked successfully!")

        utils.write_artifact(
            storage,
            result_type,
            spec.output_content_paths[0],
            spec.output_metadata_paths[0],
            result,
            system_metadata=system_metadata,
        )

        # Check if any of the written results were blacklisted and there should fail
        # the workflow.
        if spec.blacklisted_outputs is not None and any(
            json.dumps(res) in spec.blacklisted_outputs for res in results
        ):
            exec_state.status = ExecutionStatus.FAILED
            exec_state.failure_type = FailureType.USER
            exec_state.error = Error(
                context="",
                tip=TIP_BLACKLISTED_OUTPUT,
            )
            utils.write_exec_state(storage, spec.metadata_path, exec_state)

            print(f"Failed with user error. Full Logs:\n{exec_state.json()}")
            sys.exit(1)
        else:
            exec_state.status = ExecutionStatus.SUCCEEDED
            utils.write_exec_state(storage, spec.metadata_path, exec_state)
            print(f"Succeeded! Full logs: {exec_state.json()}")

    except Exception as e:
        exec_state.status = ExecutionStatus.FAILED
        exec_state.failure_type = FailureType.SYSTEM
        exec_state.error = Error(
            context=exception_traceback(e),
            tip=TIP_UNKNOWN_ERROR,
        )
        print(f"Failed with system error. Full Logs:\n{exec_state.json()}")
        utils.write_exec_state(storage, spec.metadata_path, exec_state)
        sys.exit(1)
