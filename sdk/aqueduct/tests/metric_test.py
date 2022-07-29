import json
import sys
from io import StringIO
from unittest.mock import MagicMock

from aqueduct.decorator import check, metric
from aqueduct.enums import ExecutionStatus
from aqueduct.metric_artifact import MetricArtifact
from aqueduct.responses import ArtifactResult, MetricArtifactResult, OperatorResult, PreviewResponse
from aqueduct.tests.utils import default_table_artifact
from aqueduct.utils import delete_zip_folder_and_file, generate_uuid

from aqueduct import api_client

metric_op_name = "metric_fn"
description = f"{metric_op_name} description"
metric_artifact_name = f"{metric_op_name} artifact"
zip_folder = f"{metric_op_name}_aqueduct_metric"


@metric(description=description)
def metric_fn(df):
    pass


def test_metric():
    output = 10
    op_name = "op"
    op_id = generate_uuid()
    artifact_id = generate_uuid()
    artifact_name = "artifact"
    api_client.__GLOBAL_API_CLIENT__.configure("", "")

    metric_input = default_table_artifact(
        operator_name=op_name,
        operator_id=op_id,
        artifact_name=artifact_name,
        artifact_id=artifact_id,
    )
    dag = metric_input._dag

    try:
        metric_output: MetricArtifact = metric_fn(metric_input)
    finally:
        delete_zip_folder_and_file(zip_folder)

    status = ExecutionStatus.SUCCEEDED
    operator_results = {
        op_id: OperatorResult(),
    }
    artifact_results = {
        metric_output.id(): ArtifactResult(metric=MetricArtifactResult(val=output)),
    }
    preview_output = PreviewResponse(
        status=status,
        operator_results=operator_results,
        artifact_results=artifact_results,
    )
    api_client.__GLOBAL_API_CLIENT__.preview = MagicMock(return_value=preview_output)

    metric_val = metric_output.get()

    api_client.__GLOBAL_API_CLIENT__.preview.assert_called_with(dag=dag)
    assert len(dag.operators) == len(dag.artifacts)
    assert len(dag.operators) == 2

    artifact_check = {
        artifact_name: {
            "float": None,
            "table": {},
        },
        metric_artifact_name: {"float": {}, "table": None},
    }

    for artifact in dag.artifacts:
        artifact = dag.artifacts[artifact]
        assert artifact.name in artifact_check.keys()
        assert artifact.spec.float == artifact_check[artifact.name]["float"]
        assert artifact.spec.table == artifact_check[artifact.name]["table"]
        if artifact.name == metric_artifact_name:
            metric_artifact_id = artifact.id

    operator_check = {
        op_name: {
            "inputs": [],
            "outputs": [artifact_id],
            "description": "",
        },
        metric_op_name: {
            "inputs": [artifact_id],
            "outputs": [metric_artifact_id],
            "description": description,
        },
    }

    for operator in dag.operators:
        operator = dag.operators[operator]
        assert operator.name in operator_check.keys()
        assert operator.description == operator_check[operator.name]["description"]
        for artifacts, key in [
            (operator.inputs, "inputs"),
            (operator.outputs, "outputs"),
        ]:
            assert len(artifacts) == len(operator_check[operator.name][key])
            for artifact in operator_check[operator.name][key]:
                assert artifact in artifacts

    assert metric_val == output


def test_metrics_and_checks_on_table_describe():
    metric_input = default_table_artifact()

    try:
        metric_output: MetricArtifact = metric_fn(metric_input)
    finally:
        delete_zip_folder_and_file(zip_folder)

    check_description = "Check description"

    @check(description=check_description)
    def check_fn(metric_output):
        return metric_output > 0

    check_name = "check_fn"
    check_fn(metric_output)

    redirect_stdout = StringIO()
    stdout = sys.stdout
    sys.stdout = redirect_stdout
    metric_input.describe()
    describe_table = redirect_stdout.getvalue()
    sys.stdout = stdout

    output_dict = json.loads("\n".join(describe_table.split("\n")[1:]))

    assert len(output_dict["Metrics"]) == 1
    metric_descr = output_dict["Metrics"][0]
    assert metric_descr["Label"] == metric_op_name
    assert metric_descr["Description"] == description
    assert len(metric_descr["Checks"]) == 1
    metric_check = metric_descr["Checks"][0]
    assert metric_check["Label"] == check_name
    assert metric_check["Description"] == check_description
    assert "Level" in metric_check
