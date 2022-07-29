from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from aqueduct.artifact import ArtifactSpec
from aqueduct.check_artifact import CheckArtifact
from aqueduct.constants.metrics import SYSTEM_METRICS_INFO
from aqueduct.dag import (
    DAG,
    AddOrReplaceOperatorDelta,
    RemoveCheckOperatorDelta,
    SubgraphDAGDelta,
    UpdateParametersDelta,
    apply_deltas_to_dag,
)
from aqueduct.enums import CheckSeverity, FunctionGranularity, FunctionType, OperatorType
from aqueduct.error import AqueductError, InvalidIntegrationException
from aqueduct.generic_artifact import Artifact
from aqueduct.metric_artifact import MetricArtifact
from aqueduct.operators import (
    CheckSpec,
    FunctionSpec,
    LoadSpec,
    MetricSpec,
    Operator,
    OperatorSpec,
    SaveConfig,
    SystemMetricSpec,
)
from aqueduct.utils import (
    artifact_name_from_op_name,
    format_header_for_print,
    generate_uuid,
    get_checks_for_op,
    get_description_for_check,
    get_description_for_metric,
    serialize_function,
)
from great_expectations.core import ExpectationConfiguration
from great_expectations.core.batch import RuntimeBatchRequest
from great_expectations.data_context import BaseDataContext
from great_expectations.data_context.types.base import (
    DataContextConfig,
    DatasourceConfig,
    FilesystemStoreBackendDefaults,
)
from great_expectations.validator.validator import Validator
from ruamel import yaml

import aqueduct
from aqueduct import api_client

OutputArtifact = Union[MetricArtifact, CheckArtifact]


class TableArtifact(Artifact):
    """This class represents a computed table within the flow's DAG.

    Any `@op`-annotated python function that returns a dataframe will
    return this class when that function is called called.

    Examples:
        >>> @op
        >>> def predict(df):
        >>>     return predictions
        >>>
        >>> output_artifact = predict(input_artifact)

        The contents of these artifacts can be manifested locally or written to an
        integration:

        >>> df = output_artifact.get()
        >>> print(df.head())
        >>> output_artifact.save(warehouse.config(table_name="output_table"))
    """

    def __init__(self, dag: DAG, artifact_id: uuid.UUID, from_flow_run: bool = False):
        self._dag = dag
        self._artifact_id = artifact_id
        # This parameter indicates whether the artifact is fetched from flow-run or not.
        self._from_flow_run = from_flow_run

    def get(self, parameters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """Materializes TableArtifact into an actual dataframe.

        Args:
            parameters:
                A map from parameter name to its custom value, to be used when evaluating
                this artifact.

        Returns:
            A dataframe containing the tabular contents of this artifact.

        Raises:
            InvalidRequestError:
                An error occurred because of an issue with the user's code or inputs.
            InternalServerError:
                An unexpected error occurred within the Aqueduct cluster.
        """
        dag = apply_deltas_to_dag(
            self._dag,
            deltas=[
                SubgraphDAGDelta(
                    artifact_ids=[self._artifact_id],
                    include_load_operators=False,
                ),
                UpdateParametersDelta(
                    parameters=parameters,
                ),
            ],
            make_copy=True,
        )

        preview_resp = api_client.__GLOBAL_API_CLIENT__.preview(dag=dag)
        artifact_result = preview_resp.artifact_results[self._artifact_id]

        if artifact_result.table:
            # Translate the previewed table in a dataframe.
            return pd.DataFrame(json.loads(artifact_result.table.data)["data"])
        else:
            raise AqueductError("Artifact does not have table.")

    def head(self, n: int = 5, parameters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """Returns a preview of the table artifact.

        >>> db = client.integration(name="demo/")
        >>> customer_data = db.sql("SELECT * from customers")
        >>> churn_predictions = predict_churn(customer_data)
        >>> churn_predictions.head()

        Args:
            n:
                the number of row previewed. Default to 5.
        Returns:
            A dataframe containing the tabular contents of this artifact.
        """
        df = self.get(parameters=parameters)
        return df.head(n)

    def save(self, config: SaveConfig) -> None:
        """Configure this artifact to be written to a specific integration after its computed.

        >>> db = client.integration(name="demo/")
        >>> customer_data = db.sql("SELECT * from customers")
        >>> churn_predictions = predict_churn(customer_data)
        >>> churn_predictions.save(config=db.config(table="churn_predictions"))

        Args:
            config:
                SaveConfig object generated from integration using
                the <integration>.config(...) method.
        Raises:
            InvalidIntegrationException:
                An error occurred because the requested integration could not be
                found.
        """
        integration_info = config.integration_info
        integration_load_params = config.parameters
        integrations_map = api_client.__GLOBAL_API_CLIENT__.list_integrations()

        if integration_info.name not in integrations_map:
            raise InvalidIntegrationException("Not connected to db %s!" % integration_info.name)

        # Add the load operator as a terminal node.
        apply_deltas_to_dag(
            self._dag,
            deltas=[
                AddOrReplaceOperatorDelta(
                    op=Operator(
                        id=generate_uuid(),
                        name="%s Loader" % integration_info.name,
                        description="",
                        spec=OperatorSpec(
                            load=LoadSpec(
                                service=integration_info.service,
                                integration_id=integration_info.id,
                                parameters=integration_load_params,
                            )
                        ),
                        inputs=[self._artifact_id],
                    ),
                    output_artifacts=[],
                )
            ],
        )

    PRESET_METRIC_LIST = ["number_of_missing_values", "number_of_rows", "max", "min", "mean", "std"]

    def list_preset_metrics(self) -> List[str]:
        """Returns a list of all preset metrics available on the table artifact.
        These preset metrics can be set via the invoking the preset method on a artifact.

        Returns:
            A list of available preset metrics on a table
        """
        return self.PRESET_METRIC_LIST

    def list_system_metrics(self) -> List[str]:
        """Returns a list of all system metrics available on the table artifact.
        These system metrics can be set via the invoking the system_metric() method the table.

        Returns:
            A list of available system metrics on a table
        """
        return list(SYSTEM_METRICS_INFO.keys())

    def validate_with_expectation(
        self,
        expectation_name: str,
        expectation_args: Optional[Dict[str, Any]] = None,
        severity: CheckSeverity = CheckSeverity.WARNING,
    ) -> CheckArtifact:
        """Creates a check that validates with the table with great_expectations and its set of internal expectations.
        The expectations supported can be found here:
        https://great-expectations.readthedocs.io/en/latest/reference/glossary_of_expectations.html
        The expectations supported are only those that can support Pandas on the great_expectations backend.
        E.g. Use a expectation to check all column values are unique.
        ge_check = table.validate_with_expectation("expect_column_values_to_be_unique", {"column": "fixed_acidity"})
        ge_check.get() // True or False based on expectation passing

        Args:
            expectation_name:
                Name of built-in expectation to run with great_expectations
            expectation_args:
                Dictionary of args to pass into the expectation suite for the expectation being run.
            severity:
                Optional severity associated with the check created with this expectations

        Returns:
            A check artifact that represent the validation result of running the expectation provided on the table.
        """

        def great_expectations_check_method(table: pd.DataFrame) -> bool:
            data_context_config = DataContextConfig(
                datasources={
                    "my_pandas_datasource": DatasourceConfig(
                        class_name="PandasDatasource",
                    )
                },
                store_backend_defaults=FilesystemStoreBackendDefaults(root_directory="/tmp"),
            )

            context = BaseDataContext(project_config=data_context_config)

            # Create and load Expectation Suite
            expectation_suite_name = "aq_check_expectation"
            suite = context.create_expectation_suite(
                expectation_suite_name=expectation_suite_name, overwrite_existing=True
            )
            expectation_config = ExpectationConfiguration(expectation_name, expectation_args)
            suite.add_expectation(expectation_config)

            # We create a custom datasource that will allow us to load a in-memory dataframe to validate the expectation quite
            datasource_yaml = f"""
            name: my_pandas_datasource
            class_name: Datasource
            module_name: great_expectations.datasource
            execution_engine:
                module_name: great_expectations.execution_engine
                class_name: PandasExecutionEngine
            data_connectors:
                aq_runtime_dataconnecter:
                    class_name: RuntimeDataConnector
                    batch_identifiers:
                        - default_identifier_name
            """
            context.add_datasource(**yaml.load(datasource_yaml, Loader=yaml.Loader))

            df: pd.DataFrame = table
            runtime_batch_request = RuntimeBatchRequest(
                datasource_name="my_pandas_datasource",
                data_connector_name="aq_runtime_dataconnecter",
                data_asset_name="aq_table_check",
                runtime_parameters={"batch_data": df},
                batch_identifiers={"default_identifier_name": "aq_table_check"},
            )

            # Constructing Validator by passing in RuntimeBatchRequest
            my_validator: Validator = context.get_validator(
                batch_request=runtime_batch_request,
                expectation_suite=suite,
            )

            # Run validation to return the result
            result = my_validator.validate()
            return bool(result.success)

        zip_file = serialize_function(great_expectations_check_method)
        function_spec = FunctionSpec(
            type=FunctionType.FILE,
            granularity=FunctionGranularity.TABLE,
            file=zip_file,
        )
        check_spec = OperatorSpec(check=CheckSpec(level=severity, function=function_spec))
        check_name = "ge_table_check: {%s}" % expectation_name
        check_description = "Check table with built in expectations from great expectations"
        new_artifact = self._apply_operator_to_table(check_spec, check_name, check_description)
        assert isinstance(new_artifact, CheckArtifact)
        return new_artifact

    def number_of_missing_values(self, column_id: Any = None, row_id: Any = None) -> MetricArtifact:
        """Creates a metric that represents the number of missing values over a given column or row.

        Note: takes a scalar column_id/row_id and uses pandas.DataFrame.isnull() to compute value.

        Args:
            column_id:
                column identifier to find missing values for
            row_id:
                row identifier to find missing values for

        Returns:
            A metric artifact that represents the number of missing values for the row/column on the applied table artifact.
        """
        table_artifact = self._get_table_operator()
        if column_id is not None and row_id is not None:
            raise AqueductError(
                "Cannot choose both a row and a column for counting missing values over"
            )

        if column_id is None and row_id is None:
            raise AqueductError("Specify either a row or column for counting missing values over")

        if column_id is not None:

            def interal_num_missing_val_col(table: pd.DataFrame) -> float:
                return float(table[column_id].isnull().sum())

            metric_func = interal_num_missing_val_col
            metric_name = "num_col_missing_val(%s)" % column_id
            metric_description = "compute number of missing values for col %s on table %s" % (
                column_id,
                table_artifact.name,
            )
        else:

            def interal_num_missing_val_row(table: pd.DataFrame) -> float:
                return float(table.loc[row_id].isnull().sum())

            metric_func = interal_num_missing_val_row
            metric_name = "num_row_missing_val(%s)" % row_id
            metric_description = "compute number of missing values for row %s on table %s" % (
                column_id,
                table_artifact.name,
            )

        zip_file = serialize_function(metric_func)

        function_spec = FunctionSpec(
            type=FunctionType.FILE,
            granularity=FunctionGranularity.TABLE,
            file=zip_file,
        )
        op_spec = OperatorSpec(metric=MetricSpec(function=function_spec))
        new_artifact = self._apply_operator_to_table(op_spec, metric_name, metric_description)
        assert isinstance(new_artifact, MetricArtifact)
        return new_artifact

    def number_of_rows(self) -> MetricArtifact:
        """Creates a metric that represents the number of rows of this table

        Note: uses len() to determine row count over the pandas.DataFrame.

        Returns:
            A metric artifact that represents the number of rows on this table.
        """
        table_artifact = self._get_table_operator()

        def internal_num_rows_metric(table: pd.DataFrame) -> float:
            return float(len(table))

        metric_name = "num_rows"
        metric_description = "compute number of rows for table %s" % table_artifact.name
        zip_file = serialize_function(internal_num_rows_metric)

        function_spec = FunctionSpec(
            type=FunctionType.FILE,
            granularity=FunctionGranularity.TABLE,
            file=zip_file,
        )
        op_spec = OperatorSpec(metric=MetricSpec(function=function_spec))
        new_artifact = self._apply_operator_to_table(op_spec, metric_name, metric_description)
        assert isinstance(new_artifact, MetricArtifact)
        return new_artifact

    def max(self, column_id: Any) -> MetricArtifact:
        """Creates a metric that represents the maximum value over the given column

        Note: takes a scalar column_id and uses pandas.DataFrame.max to compute value.

        Args:
            column_id:
                column identifier to find max of

        Returns:
            A metric artifact that represents the max for the given column on the applied table artifact.
        """
        table_artifact = self._get_table_operator()

        def internal_max_metric(table: pd.DataFrame) -> float:
            return float(table[column_id].max())

        metric_name = "max(%s)" % column_id
        metric_description = "Max for column %s for table %s" % (
            column_id,
            table_artifact.name,
        )
        zip_file = serialize_function(internal_max_metric)

        function_spec = FunctionSpec(
            type=FunctionType.FILE,
            granularity=FunctionGranularity.TABLE,
            file=zip_file,
        )
        op_spec = OperatorSpec(metric=MetricSpec(function=function_spec))
        new_artifact = self._apply_operator_to_table(op_spec, metric_name, metric_description)
        assert isinstance(new_artifact, MetricArtifact)
        return new_artifact

    def min(self, column_id: Any) -> MetricArtifact:
        """Creates a metric that represents the minimum value over the given column

        Note: takes a scalar column_id and uses pandas.DataFrame.min to compute value.

        Args:
            column_id:
                column identifier to find min of

        Returns:
            A metric artifact that represents the min for the given column on the applied table artifact.
        """
        table_artifact = self._get_table_operator()

        def internal_min_metric(table: pd.DataFrame) -> float:
            return float(table[column_id].min())

        metric_name = "min(%s)" % column_id
        metric_description = "Min for column %s for table %s" % (
            column_id,
            table_artifact.name,
        )
        zip_file = serialize_function(internal_min_metric)

        function_spec = FunctionSpec(
            type=FunctionType.FILE,
            granularity=FunctionGranularity.TABLE,
            file=zip_file,
        )
        op_spec = OperatorSpec(metric=MetricSpec(function=function_spec))
        new_artifact = self._apply_operator_to_table(op_spec, metric_name, metric_description)
        assert isinstance(new_artifact, MetricArtifact)
        return new_artifact

    def mean(self, column_id: Any) -> MetricArtifact:
        """Creates a metric that represents the mean value over the given column

        Note: takes a scalar column_id and uses pandas.DataFrame.mean to compute value.

        Args:
            column_id:
                column identifier to compute mean of

        Returns:
            A metric artifact that represents the mean for the given column on the applied table artifact.
        """
        table_artifact = self._get_table_operator()

        def internal_mean_metric(table: pd.DataFrame) -> float:
            return float(table[column_id].mean())

        metric_name = "mean(%s)" % column_id
        metric_description = "Mean for column %s for table %s" % (
            column_id,
            table_artifact.name,
        )
        zip_file = serialize_function(internal_mean_metric)

        function_spec = FunctionSpec(
            type=FunctionType.FILE,
            granularity=FunctionGranularity.TABLE,
            file=zip_file,
        )
        op_spec = OperatorSpec(metric=MetricSpec(function=function_spec))
        new_artifact = self._apply_operator_to_table(op_spec, metric_name, metric_description)
        assert isinstance(new_artifact, MetricArtifact)
        return new_artifact

    def std(self, column_id: Any) -> MetricArtifact:
        """Creates a metric that represents the standard deviation value over the given column

        takes a scalar column_id and uses pandas.DataFrame.std to compute value

        Args:
            column_id:
                column identifier to compute standard deviation of

        Returns:
            A metric artifact that represents the standard deviation for the given column on the applied table artifact.
        """
        table_artifact = self._get_table_operator()

        def internal_std_metric(table: pd.DataFrame) -> float:
            std: float
            std = table[column_id].std()
            return std

        metric_name = "std(%s)" % column_id
        metric_description = "std for column %s for table %s" % (
            column_id,
            table_artifact.name,
        )
        zip_file = serialize_function(internal_std_metric)

        function_spec = FunctionSpec(
            type=FunctionType.FILE,
            granularity=FunctionGranularity.TABLE,
            file=zip_file,
        )
        op_spec = OperatorSpec(metric=MetricSpec(function=function_spec))
        new_artifact = self._apply_operator_to_table(op_spec, metric_name, metric_description)
        assert isinstance(new_artifact, MetricArtifact)
        return new_artifact

    def system_metric(self, metric_name: str) -> MetricArtifact:
        """Creates a system metric that represents the given system information from the previous @op that ran on the table.

        Args:
            metric_name:
                name of system metric to retrieve for the table.
                valid metrics are:
                    runtime: runtime of previous @op func in seconds
                    max_memory: maximum memory usage of previous @op func in Mb

        Returns:
            A metric artifact that represents the requested system metric
        """
        operator = self._dag.must_get_operator(with_output_artifact_id=self._artifact_id)
        system_metric_description, system_metric_unit = SYSTEM_METRICS_INFO[metric_name]
        system_metric_name = "%s %s(%s) metric" % (operator.name, metric_name, system_metric_unit)
        op_spec = OperatorSpec(system_metric=SystemMetricSpec(metric_name=metric_name))
        new_artifact = self._apply_operator_to_table(
            op_spec, system_metric_name, system_metric_description
        )
        assert isinstance(new_artifact, MetricArtifact)
        return new_artifact

    def _apply_operator_to_table(
        self,
        op_spec: OperatorSpec,
        op_name: str,
        op_description: str,
    ) -> OutputArtifact:
        output_artifact: OutputArtifact
        operator_id = generate_uuid()
        output_artifact_id = generate_uuid()
        if op_spec.metric or op_spec.system_metric:
            artifact_spec = ArtifactSpec(float={})
            output_artifact = MetricArtifact(dag=self._dag, artifact_id=output_artifact_id)
        elif op_spec.check:
            artifact_spec = ArtifactSpec(bool={})
            output_artifact = CheckArtifact(dag=self._dag, artifact_id=output_artifact_id)
        else:
            raise AqueductError("Operator spec not supported.")

        apply_deltas_to_dag(
            self._dag,
            deltas=[
                AddOrReplaceOperatorDelta(
                    op=Operator(
                        id=operator_id,
                        name=op_name,
                        description=op_description,
                        spec=op_spec,
                        inputs=[self._artifact_id],
                        outputs=[output_artifact_id],
                    ),
                    output_artifacts=[
                        aqueduct.artifact.Artifact(
                            id=output_artifact_id,
                            name=artifact_name_from_op_name(op_name),
                            spec=artifact_spec,
                        )
                    ],
                ),
            ],
        )

        return output_artifact

    def _get_table_operator(self) -> Operator:
        table_artifact = self._dag.get_operator(with_output_artifact_id=self._artifact_id)
        if table_artifact is None:
            raise AqueductError("table artifact no longer valid to associate metric with")

        return table_artifact

    def describe(self) -> None:
        """Prints out a human-readable description of the table artifact."""

        input_operator = self._dag.must_get_operator(with_output_artifact_id=self._artifact_id)
        load_operators = self._dag.list_operators(
            filter_to=[OperatorType.LOAD],
            on_artifact_id=self._artifact_id,
        )

        metric_operators = self._dag.list_operators(
            filter_to=[OperatorType.METRIC],
            on_artifact_id=self._artifact_id,
        )

        check_operators = get_checks_for_op(input_operator, self._dag)

        readable_dict = super()._describe()
        readable_dict.update(
            {
                "Metrics": [get_description_for_metric(op, self._dag) for op in metric_operators],
                "Checks": [get_description_for_check(op) for op in check_operators],
                "Destinations": [
                    {
                        "Name": op.name,
                        "Description": op.description,
                        "Spec": op.spec.json(exclude_none=True),
                    }
                    for op in load_operators
                    if op.spec.load is not None
                ],
            }
        )
        print(format_header_for_print(f"'{input_operator.name}' Table Artifact"))
        print(json.dumps(readable_dict, sort_keys=False, indent=4))

    def remove_check(self, name: str) -> None:
        """Remove a check on this artifact by name.

        Raises:
            InvalidUserActionException: if a matching check operator could not be found.
        """
        apply_deltas_to_dag(
            self._dag,
            deltas=[
                RemoveCheckOperatorDelta(check_name=name, artifact_id=self._artifact_id),
            ],
        )
