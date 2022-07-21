from aqueduct.check_artifact import CheckArtifact
from aqueduct.decorator import check, metric, op
from aqueduct.metric_artifact import MetricArtifact
from aqueduct.table_artifact import DataArtifact
from aqueduct.tests.utils import default_table_artifact
from aqueduct.utils import delete_zip_folder_and_file


def test_decorators_with_without_parentheses():
    inp = default_table_artifact()

    @op()
    def op_fn_with_parentheses(df):
        pass

    @op
    def op_fn_without_parentheses(df):
        pass

    @metric()
    def metric_fn_with_parentheses(df):
        pass

    @metric
    def metric_fn_without_parentheses(df):
        pass

    @check()
    def check_fn_with_parentheses(df):
        pass

    @check
    def check_fn_without_parentheses(df):
        pass

    w_parentheses = "with parentheses"
    wo_parentheses = "without parentheses"
    output_type = "output_type"
    label = "label"

    decorators = {
        "op": {
            w_parentheses: op_fn_with_parentheses,
            wo_parentheses: op_fn_without_parentheses,
            output_type: DataArtifact,
            label: lambda name: f"{name}_aqueduct",
        },
        "metric": {
            w_parentheses: metric_fn_with_parentheses,
            wo_parentheses: metric_fn_without_parentheses,
            output_type: MetricArtifact,
            label: lambda name: f"{name}_aqueduct_metric",
        },
        "check": {
            w_parentheses: check_fn_with_parentheses,
            wo_parentheses: check_fn_without_parentheses,
            output_type: CheckArtifact,
            label: lambda name: f"{name}_aqueduct_check",
        },
    }

    for decorator in decorators.keys():
        decorator_data = decorators[decorator]
        expected_output_type = decorator_data[output_type]
        for inp_type in [w_parentheses, wo_parentheses]:
            fn = decorator_data[inp_type]
            name = f"{decorator}_fn_{inp_type.replace(' ', '_')}"
            try:
                fn_output = fn(inp)
            finally:
                delete_zip_folder_and_file(decorator_data[label](name))
            assert isinstance(
                fn_output, expected_output_type
            ), f"Expected: {expected_output_type}, Got: {type(fn_output)} for decorator {decorator} {inp_type}"
