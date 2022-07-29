import json
import re
from typing import Optional, Union

import pandas as pd
from aqueduct.artifact import Artifact, ArtifactSpec
from aqueduct.dag import DAG, AddOrReplaceOperatorDelta, apply_deltas_to_dag
from aqueduct.enums import LoadUpdateMode, ServiceType
from aqueduct.error import InvalidUserArgumentException
from aqueduct.integrations.integration import Integration, IntegrationInfo
from aqueduct.operators import (
    ExtractSpec,
    Operator,
    OperatorSpec,
    RelationalDBExtractParams,
    RelationalDBLoadParams,
    SaveConfig,
)
from aqueduct.table_artifact import TableArtifact
from aqueduct.utils import artifact_name_from_op_name, generate_uuid

LIST_TABLES_QUERY_PG = "SELECT tablename, tableowner FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';"
LIST_TABLES_QUERY_SNOWFLAKE = "SELECT table_name AS \"tablename\", table_owner AS \"tableowner\" FROM information_schema.tables WHERE table_schema != 'INFORMATION_SCHEMA' AND table_type = 'BASE TABLE';"
LIST_TABLES_QUERY_MYSQL = "SELECT table_name FROM INFORMATION_SCHEMA.TABLES WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('mysql', 'sys', 'performance_schema');"
LIST_TABLES_QUERY_SQLSERVER = (
    "SELECT table_name FROM INFORMATION_SCHEMA.TABLES WHERE table_type = 'BASE TABLE';"
)
LIST_TABLES_QUERY_BIGQUERY = "SELECT schema_name FROM information_schema.schemata;"
GET_TABLE_QUERY = "select * from %s"
LIST_TABLES_QUERY_SQLITE = "SELECT name FROM sqlite_master WHERE type='table';"

# Regular Expression that matches any substring appearance with
# "{{ }}" and a word inside with optional space in front or after
# Potential Matches: "{{today}}", "{{ today  }}""
#
# Duplicated in the Python operators at `src/python/aqueduct_executor/operators/connectors/tabular/extract.py`
# Make sure the two are in sync.
TAG_PATTERN = r"{{\s*[\w-]+\s*}}"

# A dictionary of built-in tags to their replacement0 string functions.
#
# Duplicated in spirit by the Python operators at `src/python/aqueduct_executor/operators/connectors/tabular/extract.py`
# Make sure the two are in sync.
BUILT_IN_EXPANSIONS = {"today"}


class RelationalDBIntegration(Integration):
    """
    Class for RealtionalDB integrations.
    """

    def __init__(self, dag: DAG, metadata: IntegrationInfo):
        self._dag = dag
        self._metadata = metadata

    def list_tables(self) -> pd.DataFrame:
        """
        Lists the tables available in the RealtionalDB integration.

        Returns:
            pd.DataFrame of available tables.
        """
        if self._metadata.service in [
            ServiceType.POSTGRES,
            ServiceType.AQUEDUCTDEMO,
            ServiceType.REDSHIFT,
        ]:
            list_tables_query = LIST_TABLES_QUERY_PG
        elif self._metadata.service == ServiceType.SNOWFLAKE:
            list_tables_query = LIST_TABLES_QUERY_SNOWFLAKE
        elif self._metadata.service in [ServiceType.MYSQL, ServiceType.MARIADB]:
            list_tables_query = LIST_TABLES_QUERY_MYSQL
        elif self._metadata.service == ServiceType.SQLSERVER:
            list_tables_query = LIST_TABLES_QUERY_SQLSERVER
        elif self._metadata.service == ServiceType.BIGQUERY:
            list_tables_query = LIST_TABLES_QUERY_BIGQUERY
        elif self._metadata.service == ServiceType.SQLITE:
            list_tables_query = LIST_TABLES_QUERY_SQLITE

        sql_artifact = self.sql(query=list_tables_query)
        return sql_artifact.get()

    def table(self, name: str) -> pd.DataFrame:
        """
        Retrieves a table from a RealtionalDB integration.

        Args:
            name:
                The name of the table to retrieve.

        Returns:
            pd.DataFrame of the table to retrieve.
        """
        sql_artifact = self.sql(query=GET_TABLE_QUERY % name)
        return sql_artifact.get()

    def sql(
        self,
        query: Union[str, RelationalDBExtractParams],
        name: Optional[str] = None,
        description: str = "",
    ) -> TableArtifact:
        """
        Runs a SQL query against the RelationalDB integration.

        Args:
            query:
                The query to run.
            name:
                Name of the query.
            description:
                Description of the query.

        Returns:
            TableArtifact representing result of the SQL query.
        """
        integration_info = self._metadata

        # The sql operator name defaults to "[integration name] query 1". If another
        # sql operator already exists with that name, we'll continue bumping the suffix
        # until the sql operator is unique. If an explicit name is provided, we will
        # overwrite the existing one.
        sql_op_name = name

        default_sql_op_prefix = "%s query" % integration_info.name
        default_sql_op_index = 1
        while sql_op_name is None:
            candidate_op_name = default_sql_op_prefix + " %d" % default_sql_op_index
            colliding_op = self._dag.get_operator(with_name=candidate_op_name)
            if colliding_op is None:
                sql_op_name = candidate_op_name  # break out of the loop!
            default_sql_op_index += 1

        assert sql_op_name is not None

        extract_params = query
        if isinstance(extract_params, str):
            extract_params = RelationalDBExtractParams(
                query=extract_params,
            )

        # Find any tags that need to be expanded in the query, and add the parameters that correspond
        # to these tags as inputs to this operator. The orchestration engine will perform the replacement at runtime.
        sql_input_artifact_ids = []
        if extract_params.query is not None:
            matches = re.findall(TAG_PATTERN, extract_params.query)
            for match in matches:
                param_name = match.strip(" {}")
                param_op = self._dag.get_operator(with_name=param_name)
                if param_op is None:
                    # If it is a built-in tag, we can ignore it for now, since the python operators will perform the expansion.
                    if param_name in BUILT_IN_EXPANSIONS:
                        continue

                    raise InvalidUserArgumentException(
                        "There is no parameter defined with name `%s`." % param_name,
                    )

                # Check that the parameter corresponds to a string value.
                assert param_op.spec.param is not None
                param_val = json.loads(param_op.spec.param.val)
                if not isinstance(param_val, str):
                    raise InvalidUserArgumentException(
                        "The parameter `%s` must be defined as a string. Instead, got type %s"
                        % (param_name, type(param_val).__name__)
                    )
                assert len(param_op.outputs) == 1
                sql_input_artifact_ids.append(param_op.outputs[0])

        sql_operator_id = generate_uuid()
        sql_output_artifact_id = generate_uuid()
        apply_deltas_to_dag(
            self._dag,
            deltas=[
                AddOrReplaceOperatorDelta(
                    op=Operator(
                        id=sql_operator_id,
                        name=sql_op_name,
                        description=description,
                        spec=OperatorSpec(
                            extract=ExtractSpec(
                                service=integration_info.service,
                                integration_id=integration_info.id,
                                parameters=extract_params,
                            )
                        ),
                        inputs=sql_input_artifact_ids,
                        outputs=[sql_output_artifact_id],
                    ),
                    output_artifacts=[
                        Artifact(
                            id=sql_output_artifact_id,
                            name=artifact_name_from_op_name(sql_op_name),
                            spec=ArtifactSpec(table={}),
                        ),
                    ],
                ),
            ],
        )

        return TableArtifact(
            dag=self._dag,
            artifact_id=sql_output_artifact_id,
        )

    def config(self, table: str, update_mode: LoadUpdateMode) -> SaveConfig:
        """
        Configuration for saving to RelationalDB Integration.

        Arguments:
            table:
                Table to save to.
            update_mode:
                The update mode to use when saving the artifact as a relational table.
                Possible values are: APPEND, REPLACE, or FAIL.
        Returns:
            SaveConfig object to use in TableArtifact.save()
        """
        return SaveConfig(
            integration_info=self._metadata,
            parameters=RelationalDBLoadParams(table=table, update_mode=update_mode),
        )

    def describe(self) -> None:
        """
        Prints out a human-readable description of the SQL integration.
        """
        print("==================== SQL Integration =============================")
        print("Integration Information:")
        self._metadata.describe()
        print("Integration Table List Preview:")
        print(self.list_tables()["name"].head().to_string())
        print("(only first 5 tables are shown)")
