import argparse
import base64
import json
import sys
import traceback

from pydantic import parse_obj_as

from aqueduct_executor.operators.connectors.tabular import common, config, connector, spec
from aqueduct_executor.operators.utils import enums, utils
from aqueduct_executor.operators.utils.storage.parse import parse_storage
from aqueduct_executor.operators.utils.storage.storage import Storage


def run(spec: spec.Spec, storage: Storage):
    """
    Runs one of the following connector operations:
    - authenticate
    - extract
    - load
    - discover

    Arguments:
    - spec: The spec provided for this operator.
    - storage: An execution storage to use for reading or writing artifacts.
    """

    op = setup_connector(spec.connector_name, spec.connector_config)

    if spec.type == enums.JobType.AUTHENTICATE:
        run_authenticate(op)
    elif spec.type == enums.JobType.EXTRACT:
        run_extract(spec, op, storage)
    elif spec.type == enums.JobType.LOAD:
        run_load(spec, op, storage)
    elif spec.type == enums.JobType.DISCOVER:
        run_discover(spec, op, storage)
    else:
        raise Exception("Unknown job: %s" % spec.type)


def run_authenticate(op: connector.TabularConnector):
    op.authenticate()


def run_extract(spec: spec.ExtractSpec, op: connector.TabularConnector, storage: Storage):
    df = op.extract(spec.parameters)
    utils.write_artifacts(
        storage,
        [spec.output_content_path],
        [spec.output_metadata_path],
        [df],
        {},
        [utils.OutputArtifactType.TABLE],
    )


def run_load(spec: spec.LoadSpec, op: connector.TabularConnector, storage: Storage):
    inputs = utils.read_artifacts(
        storage,
        [spec.input_content_path],
        [spec.input_metadata_path],
        [utils.InputArtifactType.TABLE],
    )
    if len(inputs) != 1:
        raise Exception("Expected 1 input artifact, but got %d" % len(inputs))
    op.load(spec.parameters, inputs[0])


def run_discover(spec: spec.DiscoverSpec, op: connector.TabularConnector, storage: Storage):
    tables = op.discover()
    utils.write_discover_results(storage, spec.output_content_path, tables)


def setup_connector(
    connector_name: common.Name, connector_config: config.Config
) -> connector.TabularConnector:
    if connector_name == common.Name.AQUEDUCT_DEMO or connector_name == common.Name.POSTGRES:
        from aqueduct_executor.operators.connectors.tabular.postgres import (
            PostgresConnector as OpConnector,
        )
    elif connector_name == common.Name.SNOWFLAKE:
        from aqueduct_executor.operators.connectors.tabular.snowflake import (
            SnowflakeConnector as OpConnector,
        )
    elif connector_name == common.Name.BIG_QUERY:
        from aqueduct_executor.operators.connectors.tabular.bigquery import (
            BigQueryConnector as OpConnector,
        )
    elif connector_name == common.Name.REDSHIFT:
        from aqueduct_executor.operators.connectors.tabular.redshift import (
            RedshiftConnector as OpConnector,
        )
    elif connector_name == common.Name.SQL_SERVER:
        from aqueduct_executor.operators.connectors.tabular.sql_server import (
            SqlServerConnector as OpConnector,
        )
    elif connector_name == common.Name.MYSQL:
        from aqueduct_executor.operators.connectors.tabular.mysql import (
            MySqlConnector as OpConnector,
        )
    elif connector_name == common.Name.MARIA_DB:
        from aqueduct_executor.operators.connectors.tabular.maria_db import (
            MariaDbConnector as OpConnector,
        )
    elif connector_name == common.Name.AZURE_SQL:
        from aqueduct_executor.operators.connectors.tabular.azure_sql import (
            AzureSqlConnector as OpConnector,
        )
    elif connector_name == common.Name.S3:
        from aqueduct_executor.operators.connectors.tabular.s3 import S3Connector as OpConnector
    elif connector_name == common.Name.SQLITE:
        from aqueduct_executor.operators.connectors.tabular.sqlite import (
            SqliteConnector as OpConnector,
        )
    else:
        raise Exception("Unknown connector name: %s" % connector_name)

    return OpConnector(config=connector_config)


def _parse_spec(spec_json: str) -> spec.Spec:
    """
    Parses a JSON string into a spec.Spec.
    """
    data = json.loads(spec_json)

    print("Job Spec: \n{}".format(json.dumps(data, indent=4)))

    return parse_obj_as(spec.Spec, data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--spec", required=True)
    args = parser.parse_args()

    spec_json = base64.b64decode(args.spec)
    spec = _parse_spec(spec_json)

    print("Started %s job: %s" % (spec.type, spec.name))

    storage = parse_storage(spec.storage_config)

    try:
        run(spec, storage)
        # Write operator execution metadata
        utils.write_operator_metadata(storage, spec.metadata_path, err="", logs={})
    except Exception as e:
        traceback.print_exc()
        err_msg = str(e)
        utils.write_operator_metadata(storage, spec.metadata_path, err=err_msg, logs={})
        sys.exit(1)
