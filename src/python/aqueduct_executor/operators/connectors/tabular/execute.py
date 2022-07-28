import sys

import pandas as pd
from aqueduct_executor.operators.connectors.tabular import common, config, connector, extract
from aqueduct_executor.operators.connectors.tabular.spec import (
    AQUEDUCT_DEMO_NAME,
    DiscoverSpec,
    ExtractSpec,
    LoadSpec,
    LoadTableSpec,
    Spec,
)
from aqueduct_executor.operators.utils import enums, utils
from aqueduct_executor.operators.utils.execution import (
    TIP_DEMO_CONNECTION,
    TIP_EXTRACT,
    TIP_INTEGRATION_CONNECTION,
    TIP_LOAD,
    TIP_UNKNOWN_ERROR,
    Error,
    ExecutionState,
    Logs,
    exception_traceback,
)
from aqueduct_executor.operators.utils.storage.parse import parse_storage
from aqueduct_executor.operators.utils.storage.storage import Storage
from typing import Any


def run(spec: Spec) -> None:
    """
    Runs one of the following connector operations:
    - authenticate
    - extract
    - load
    - load-table
    - discover

    Arguments:
    - spec: The spec provided for this operator.
    - storage: An execution storage to use for reading or writing artifacts.
    """
    print("Started %s job: %s" % (spec.type, spec.name))

    storage = parse_storage(spec.storage_config)
    exec_state = ExecutionState(user_logs=Logs())

    try:
        _execute(spec, storage, exec_state)
        # Write operator execution metadata
        if exec_state.status != enums.ExecutionStatus.FAILED:
            exec_state.status = enums.ExecutionStatus.SUCCEEDED
        utils.write_exec_state(storage, spec.metadata_path, exec_state)
    except Exception as e:
        exec_state.status = enums.ExecutionStatus.FAILED
        exec_state.failure_type = enums.FailureType.SYSTEM
        exec_state.error = Error(context=exception_traceback(e), tip=TIP_UNKNOWN_ERROR)
        print(f"Failed with system error. Full Logs:\n{exec_state.json()}")
        utils.write_exec_state(storage, spec.metadata_path, exec_state)
        sys.exit(1)


def _execute(spec: Spec, storage: Storage, exec_state: ExecutionState) -> None:
    op = setup_connector(spec.connector_name, spec.connector_config)

    if spec.type == enums.JobType.AUTHENTICATE:
        run_authenticate(op, exec_state, is_demo=(spec.name == AQUEDUCT_DEMO_NAME))
    elif spec.type == enums.JobType.EXTRACT:
        run_extract(spec, op, storage, exec_state)
    elif spec.type == enums.JobType.LOADTABLE:
        run_load_table(spec, op, storage)
    elif spec.type == enums.JobType.LOAD:
        run_load(spec, op, storage, exec_state)
    elif spec.type == enums.JobType.DISCOVER:
        run_discover(spec, op, storage)
    else:
        raise Exception("Unknown job: %s" % spec.type)


def run_authenticate(
    op: connector.StorageConnector,
    exec_state: ExecutionState,
    is_demo: bool,
) -> None:
    @exec_state.user_fn_redirected(
        failure_tip=TIP_DEMO_CONNECTION if is_demo else TIP_INTEGRATION_CONNECTION
    )
    def _authenticate() -> None:
        op.authenticate()

    _authenticate()


def run_extract(
    spec: ExtractSpec, op: connector.StorageConnector, storage: Storage, exec_state: ExecutionState
) -> None:
    extract_params = spec.parameters

    # Search for user-defined placeholder if this is a relational query, and replace them with
    # the appropriate values.
    if isinstance(extract_params, extract.RelationalParams):
        assert len(spec.input_param_names) == len(spec.input_content_paths)
        input_vals, _ = utils.read_artifacts(
            storage,
            spec.input_content_paths,
            spec.input_metadata_paths,
        )
        assert all(
            isinstance(param_val, str) for param_val in input_vals
        ), "Parameter value must be a string."

        parameters = dict(zip(spec.input_param_names, input_vals))
        extract_params.expand_placeholders(parameters)

    @exec_state.user_fn_redirected(failure_tip=TIP_EXTRACT)
    def _extract() -> Any:
        return op.extract(spec.parameters)

    output = _extract()

    output_artifact_type = enums.ArtifactType.TABULAR
    if isinstance(extract_params, extract.S3Params):
        output_artifact_type = extract_params.artifact_type
        # If the type of the output is tuple, then it could be a multi-file S3 request so we
        # overwrite the output type to tuple.
        if isinstance(output, tuple):
            output_artifact_type = enums.ArtifactType.TUPLE

    if exec_state.status != enums.ExecutionStatus.FAILED:
        utils.write_artifact(
            storage,
            output_artifact_type,
            spec.output_content_path,
            spec.output_metadata_path,
            output,
            system_metadata={},
        )


def run_load(
    spec: LoadSpec, op: connector.StorageConnector, storage: Storage, exec_state: ExecutionState
) -> None:
    inputs, input_types = utils.read_artifacts(
        storage,
        [spec.input_content_path],
        [spec.input_metadata_path],
    )
    if len(inputs) != 1:
        raise Exception("Expected 1 input artifact, but got %d" % len(inputs))

    @exec_state.user_fn_redirected(failure_tip=TIP_LOAD)
    def _load() -> None:
        op.load(spec.parameters, inputs[0], input_types[0])

    _load()


def run_load_table(spec: LoadTableSpec, op: connector.StorageConnector, storage: Storage) -> None:
    df = utils._read_csv(storage, spec.csv)
    op.load(spec.load_parameters.parameters, df)


def run_discover(spec: DiscoverSpec, op: connector.StorageConnector, storage: Storage) -> None:
    tables = op.discover()
    utils.write_discover_results(storage, spec.output_content_path, tables)


def setup_connector(
    connector_name: common.Name, connector_config: config.Config
) -> connector.StorageConnector:
    # prevent isort from moving around type: ignore comments which will cause mypy issues.
    # isort: off
    if connector_name == common.Name.AQUEDUCT_DEMO or connector_name == common.Name.POSTGRES:
        from aqueduct_executor.operators.connectors.tabular.postgres import (
            PostgresConnector as OpConnector,
        )
    elif connector_name == common.Name.SNOWFLAKE:
        from aqueduct_executor.operators.connectors.tabular.snowflake import (  # type: ignore
            SnowflakeConnector as OpConnector,
        )
    elif connector_name == common.Name.BIG_QUERY:
        from aqueduct_executor.operators.connectors.tabular.bigquery import (  # type: ignore
            BigQueryConnector as OpConnector,
        )
    elif connector_name == common.Name.REDSHIFT:
        from aqueduct_executor.operators.connectors.tabular.redshift import (  # type: ignore
            RedshiftConnector as OpConnector,
        )
    elif connector_name == common.Name.SQL_SERVER:
        from aqueduct_executor.operators.connectors.tabular.sql_server import (  # type: ignore
            SqlServerConnector as OpConnector,
        )
    elif connector_name == common.Name.MYSQL:
        from aqueduct_executor.operators.connectors.tabular.mysql import (  # type: ignore
            MySqlConnector as OpConnector,
        )
    elif connector_name == common.Name.MARIA_DB:
        from aqueduct_executor.operators.connectors.tabular.maria_db import (  # type: ignore
            MariaDbConnector as OpConnector,
        )
    elif connector_name == common.Name.AZURE_SQL:
        from aqueduct_executor.operators.connectors.tabular.azure_sql import (  # type: ignore
            AzureSqlConnector as OpConnector,
        )
    elif connector_name == common.Name.S3:
        from aqueduct_executor.operators.connectors.tabular.s3 import (  # type: ignore
            S3Connector as OpConnector,
        )
    elif connector_name == common.Name.SQLITE:
        from aqueduct_executor.operators.connectors.tabular.sqlite import (  # type: ignore
            SqliteConnector as OpConnector,
        )
    else:
        raise Exception("Unknown connector name: %s" % connector_name)

    # isort: on
    return OpConnector(config=connector_config)  # type: ignore
