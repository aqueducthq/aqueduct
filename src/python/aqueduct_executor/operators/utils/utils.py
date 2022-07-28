import io
import json
from typing import Any, Dict, List, Union

import numpy as np
import pandas as pd
from aqueduct_executor.operators.utils.enums import InputArtifactType, OutputArtifactType
from aqueduct_executor.operators.utils.execution import ExecutionState
from aqueduct_executor.operators.utils.saved_object_delete import SavedObjectDelete
from aqueduct_executor.operators.utils.storage.storage import Storage

_DEFAULT_ENCODING = "utf8"
_RUNTIME_SEC_METRIC_NAME = "runtime"
_MAX_MEMORY_MB_METRIC_NAME = "max_memory"
_METADATA_SCHEMA_KEY = "schema"
_METADATA_SYSTEM_METADATA_KEY = "system_metadata"


def _read_csv(storage: Storage, path: str) -> pd.DataFrame:
    input_bytes = storage.get(path)
    return pd.read_csv(io.BytesIO(input_bytes))


def read_artifacts(
    storage: Storage,
    input_paths: List[str],
    input_metadata_paths: List[str],
    artifact_types: List[InputArtifactType],
) -> List[Any]:
    """Returns an `Any` type because a parameters can be any jsonable, user-defined value."""

    if len(input_paths) != len(artifact_types):
        raise Exception(
            "Found inconsistent number of input paths (%d) and artifact types (%d)"
            % (
                len(input_paths),
                len(artifact_types),
            )
        )

    inputs: List[Any] = []
    for (input_path, artifact_type) in zip(input_paths, artifact_types):
        if artifact_type == InputArtifactType.TABLE:
            inputs.append(_read_tabular_input(storage, input_path))
        elif artifact_type == InputArtifactType.FLOAT:
            # TODO(ENG-1119): A float artifact currently also represents integers.
            inputs.append(_read_numeric_input(storage, input_path))
        elif artifact_type == InputArtifactType.JSON:
            inputs.append(_read_json_input(storage, input_path))
        else:
            raise Exception("Unexpected input artifact type %s", artifact_type)
    return inputs


def read_system_metadata(
    storage: Storage,
    input_metadata_paths: List[str],
) -> List[Dict[str, Any]]:
    return _read_metadata_key(storage, input_metadata_paths, _METADATA_SYSTEM_METADATA_KEY)


def _read_metadata_key(
    storage: Storage, input_metadata_paths: List[str], key_name: str
) -> List[Dict[str, Any]]:
    metadata_inputs = [_read_json_input(storage, input_path) for input_path in input_metadata_paths]
    if any(key_name not in metadata for metadata in metadata_inputs):
        raise Exception(key_name + " does not exist in input metadata.")
    return [metadata[key_name] for metadata in metadata_inputs]


# TODO: Can also the input metadata here if we wanted to use it.
def _read_tabular_input(storage: Storage, path: str) -> pd.DataFrame:
    input_bytes = storage.get(path)
    return pd.read_json(io.BytesIO(input_bytes), orient="table")


def _read_numeric_input(storage: Storage, path: str) -> Union[float, int]:
    input_bytes = storage.get(path)

    # Check if it's an integer first, because casting a float to an int in this fashion
    # will throw a ValueError.
    try:
        return int(input_bytes)
    except ValueError:
        pass
    return float(input_bytes)


def _read_json_input(storage: Storage, path: str) -> Any:
    input_bytes = storage.get(path)
    return json.loads(input_bytes)


def write_artifacts(
    storage: Storage,
    artifact_types: List[OutputArtifactType],
    output_paths: List[str],
    output_metadata_paths: List[str],
    contents: List[Any],
    system_metadata: Dict[str, str],
) -> None:
    """The same system and user-defined metadata is written for each artifact."""
    if (
        len(contents) != len(output_paths)
        or len(contents) != len(output_metadata_paths)
        or len(contents) != len(artifact_types)
    ):
        raise Exception(
            "Found inconsistent number of outputs (%d), artifact_types (%d), output paths (%d), and output metadata paths (%d)."
            % (
                len(contents),
                len(artifact_types),
                len(output_paths),
                len(output_metadata_paths),
            )
        )

    for (artifact_type, output_path, output_metadata_path, content) in zip(
        artifact_types, output_paths, output_metadata_paths, contents
    ):
        write_artifact(
            storage,
            artifact_type,
            output_path,
            output_metadata_path,
            content,
            system_metadata,
        )


def write_artifact(
    storage: Storage,
    artifact_type: OutputArtifactType,
    output_path: str,
    output_metadata_path: str,
    content: Any,
    system_metadata: Dict[str, str],
) -> None:
    output_metadata: Dict[str, Any] = {
        _METADATA_SCHEMA_KEY: [],
        _METADATA_SYSTEM_METADATA_KEY: system_metadata,
    }

    if artifact_type == OutputArtifactType.TABLE:
        if not isinstance(content, pd.DataFrame):
            raise Exception(
                "Expected output type to be Pandas Dataframe, but instead got %s"
                % type(content).__name__
            )
        output_metadata[_METADATA_SCHEMA_KEY] = [{col: str(content[col].dtype)} for col in content]
        _write_tabular_output(storage, output_path, output_metadata_path, content, output_metadata)

    elif artifact_type == OutputArtifactType.FLOAT:
        try:
            float(content)
            _write_numeric_output(
                storage, output_path, output_metadata_path, content, output_metadata
            )
        except ValueError:
            raise Exception(
                "Expected output type to be numeric, instead got %s" % type(content).__name__
            )
    elif artifact_type == OutputArtifactType.BOOL:
        if isinstance(content, bool) or isinstance(content, np.bool_):
            _write_bool_output(
                storage, output_path, output_metadata_path, bool(content), output_metadata
            )
        elif isinstance(content, pd.Series) and content.dtype == "bool":
            # We only write True if every boolean in the series is True.
            series = pd.Series(content)
            all_true = series.size - series.sum().item() == 0
            _write_bool_output(
                storage, output_path, output_metadata_path, all_true, output_metadata
            )
        else:
            raise Exception(
                "Expected output type to either a bool or a series of booleans, "
                "instead got %s" % type(content).__name__
            )

    elif artifact_type == OutputArtifactType.JSON:
        if not isinstance(content, str):
            raise Exception(
                "Expected output type to be string, instead got %s" % type(content).__name__
            )
        _write_json_output(storage, output_path, output_metadata_path, content, output_metadata)
    else:
        raise Exception("Unsupported output artifact type %s" % artifact_type)


def _write_tabular_output(
    storage: Storage,
    output_path: str,
    output_metadata_path: str,
    df: pd.DataFrame,
    output_metadata: Dict[str, Any],
) -> None:
    output_str = df.to_json(orient="table", date_format="iso", index=False)
    storage.put(output_path, bytes(output_str, encoding=_DEFAULT_ENCODING))
    storage.put(
        output_metadata_path, bytes(json.dumps(output_metadata), encoding=_DEFAULT_ENCODING)
    )


def _write_numeric_output(
    storage: Storage,
    output_path: str,
    output_metadata_path: str,
    val: Union[float, int],
    output_metadata: Dict[str, Any],
) -> None:
    """Used for metrics."""
    storage.put(output_path, bytes(str(val), encoding=_DEFAULT_ENCODING))
    storage.put(
        output_metadata_path,
        bytes(json.dumps(output_metadata), encoding=_DEFAULT_ENCODING),
    )


def _write_bool_output(
    storage: Storage,
    output_path: str,
    output_metadata_path: str,
    val: bool,
    output_metadata: Dict[str, Any],
) -> None:
    """Used for checks."""
    storage.put(output_path, bytes(str(val), encoding=_DEFAULT_ENCODING))
    storage.put(
        output_metadata_path,
        bytes(json.dumps(output_metadata), encoding=_DEFAULT_ENCODING),
    )


def _write_json_output(
    storage: Storage,
    output_path: str,
    output_metadata_path: str,
    val: str,
    output_metadata: Dict[str, Any],
) -> None:
    """Used for parameters."""
    storage.put(output_path, bytes(val, encoding=_DEFAULT_ENCODING))
    storage.put(
        output_metadata_path,
        bytes(json.dumps(output_metadata), encoding=_DEFAULT_ENCODING),
    )


def write_exec_state(
    storage: Storage,
    metadata_path: str,
    exec_state: ExecutionState,
) -> None:
    """
    Writes operator execution logs to storage.
    :param err: Any error message encountered during execution.
    :param logs: Any logs generated by this operator.
    """
    storage.put(metadata_path, bytes(exec_state.json(), encoding=_DEFAULT_ENCODING))


def write_delete_saved_objects_results(
    storage: Storage, path: str, results: Dict[str, List[SavedObjectDelete]]
) -> None:
    results_str = json.dumps(
        {
            integration: [result.__dict__ for result in results[integration]]
            for integration in results
        }
    )
    storage.put(path, bytes(results_str, encoding=_DEFAULT_ENCODING))


def write_discover_results(storage: Storage, path: str, tables: List[str]) -> None:
    table_names_str = json.dumps(tables)

    storage.put(path, bytes(table_names_str, encoding=_DEFAULT_ENCODING))
