from __future__ import annotations

import json
from typing import Callable, Any
import uuid

import pandas as pd
import aqueduct

from aqueduct.api_client import APIClient
from aqueduct.artifact import ArtifactSpec
from aqueduct.dag import (
    DAG,
    apply_deltas_to_dag,
    AddOrReplaceOperatorDelta,
    SubgraphDAGDelta,
    RemoveCheckOperatorDelta,
)
from aqueduct.enums import OperatorType, FunctionType, FunctionGranularity
from aqueduct.error import (
    InvalidIntegrationException,
    AqueductError,
)
from aqueduct.operators import (
    SaveConfig,
    Operator,
    OperatorSpec,
    LoadSpec,
    FunctionSpec,
    MetricSpec,
    SystemMetricSpec,
)
from aqueduct.utils import (
    serialize_function,
    generate_uuid,
    get_checks_for_op,
    get_description_for_check,
    get_description_for_metric,
    artifact_name_from_op_name,
)

from aqueduct.generic_artifact import Artifact
from aqueduct.metric_artifact import MetricArtifact


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

    def __init__(
        self,
        api_client: APIClient,
        dag: DAG,
        artifact_id: uuid.UUID,
    ):
        self._api_client = api_client
        self._dag = dag
        self._artifact_id = artifact_id
        self._create_internal_metrics()

    def get(self) -> pd.DataFrame:
        """Materializes TableArtifact into an actual dataframe.

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
                )
            ],
            make_copy=True,
        )

        preview_resp = self._api_client.preview(dag=dag)
        artifact_result = preview_resp.artifact_results[self._artifact_id]

        if artifact_result.table:
            # Translate the previewed table in a dataframe.
            return pd.DataFrame(json.loads(artifact_result.table.data)["data"])
        else:
            raise AqueductError("Artifact does not have table.")

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
        integrations_map = self._api_client.list_integrations()

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

        return self._apply_metric_to_table(metric_func, metric_name, metric_description)

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
        return self._apply_metric_to_table(
            internal_num_rows_metric, metric_name, metric_description
        )

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
        return self._apply_metric_to_table(internal_max_metric, metric_name, metric_description)

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
        return self._apply_metric_to_table(internal_min_metric, metric_name, metric_description)

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
        return self._apply_metric_to_table(internal_mean_metric, metric_name, metric_description)

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
        return self._apply_metric_to_table(internal_std_metric, metric_name, metric_description)

    def get_time_metric(self):
        return self._time_metric

    def _create_internal_metrics(
        self,
    ):
        print("we are being called bro")
        def internal_time_metric(table: pd.DataFrame) -> float:
            print(table)
            return 0
        
        def internal_mem_metric(table: pd.DataFrame) -> float:
            return 0
        
        self._time_metric = self._apply_system_metric_to_table(
            "internal_time_metric",
            "op runtime time"
        )

        # self._apply_metric_to_table(
        #     internal_mem_metric,
        #     "internal_mem_metric",
        #     "op mem"
        # )

    def _apply_system_metric_to_table(
        self,
        metric_name: str,
        metric_description: str,
    ) -> MetricArtifact:

        metric_spec = SystemMetricSpec(
            metricname = metric_name
        )

        dag = self._dag
        api_client = self._api_client

        operator_id = generate_uuid()
        output_artifact_id = generate_uuid()

        artifact_spec = ArtifactSpec(float={})

        apply_deltas_to_dag(
            dag,
            deltas=[
                AddOrReplaceOperatorDelta(
                    op=Operator(
                        id=operator_id,
                        name=metric_name,
                        description=metric_description,
                        spec=OperatorSpec(systemmetric=metric_spec),
                        inputs=[self._artifact_id],
                        outputs=[output_artifact_id],
                    ),
                    output_artifacts=[
                        aqueduct.artifact.Artifact(
                            id=output_artifact_id,
                            name=artifact_name_from_op_name(metric_name),
                            spec=artifact_spec,
                        )
                    ],
                ),
            ],
        )

        return MetricArtifact(api_client=api_client, dag=dag, artifact_id=output_artifact_id)

    def _get_table_operator(self) -> Operator:
        table_artifact = self._dag.get_operator(with_output_artifact_id=self._artifact_id)
        if table_artifact is None:
            raise AqueductError("table artifact no longer valid to associate metric with")

        return table_artifact

    def describe(self) -> None:
        """Prints out a human-readable description of the table artifact."""
        print("==================== TABLE ARTIFACT =============================")

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
