from functools import wraps
from typing import Any, Callable, List, Optional, Union

from aqueduct.artifact import Artifact, ArtifactSpec
from aqueduct.check_artifact import CheckArtifact
from aqueduct.dag import AddOrReplaceOperatorDelta, apply_deltas_to_dag
from aqueduct.enums import CheckSeverity, FunctionGranularity, FunctionType
from aqueduct.error import AqueductError, InvalidUserActionException
from aqueduct.metric_artifact import MetricArtifact
from aqueduct.operators import CheckSpec, FunctionSpec, MetricSpec, Operator, OperatorSpec
from aqueduct.param_artifact import ParamArtifact
from aqueduct.table_artifact import TableArtifact
from aqueduct.utils import (
    CheckFunction,
    MetricFunction,
    UserFunction,
    artifact_name_from_op_name,
    generate_uuid,
    serialize_function,
)
from pandas import DataFrame

from aqueduct import dag as dag_module

# Valid inputs and outputs to our operators.
OutputArtifact = Union[TableArtifact, MetricArtifact, CheckArtifact]
InputArtifact = Union[TableArtifact, MetricArtifact, ParamArtifact]
InputArtifactLocal = Union[TableArtifact, MetricArtifact, ParamArtifact, DataFrame]

OutputArtifactFunction = Callable[..., OutputArtifact]

# Type declarations for functions
DecoratedFunction = Callable[[UserFunction], OutputArtifactFunction]

# Type declarations for metrics
DecoratedMetricFunction = Callable[[MetricFunction], OutputArtifactFunction]

# Type declarations for checks
DecoratedCheckFunction = Callable[[CheckFunction], OutputArtifactFunction]


def _is_input_artifact(elem: Any) -> bool:
    return (
        isinstance(elem, TableArtifact)
        or isinstance(elem, MetricArtifact)
        or isinstance(elem, ParamArtifact)
    )


def wrap_spec(
    spec: OperatorSpec,
    *input_artifacts: InputArtifact,
    op_name: str,
    description: str = "",
) -> OutputArtifact:
    """Applies a python function to existing artifacts.
    The function must be named predict() on a class named "Function",
    in a file named "model.py":

    >>> class Function:
    >>>     def predict(self, *args):
    >>>         ...

    Args:
        spec:
            The spec of the operator.
        *input_artifacts:
            All the artifacts that will serve as input to the python function.
            The function must have the same number of parameters as input
            artifacts.
        op_name:
            The name of the operator that generated this artifact.
        description:
            The description for this operator.
    """
    for artifact in input_artifacts:
        if artifact._from_flow_run:
            raise InvalidUserActionException(
                "Artifact fetched from flow run can not be reused for computation"
            )

    dag = dag_module.__GLOBAL_DAG__

    # Check that all the artifact ids exist in the dag.
    for artifact in input_artifacts:
        _ = dag.must_get_artifact(artifact.id())

    operator_id = generate_uuid()
    output_artifact_id = generate_uuid()

    output_artifact: OutputArtifact

    if spec.metric:
        artifact_spec = ArtifactSpec(float={})
        output_artifact = MetricArtifact(dag=dag, artifact_id=output_artifact_id)
    elif spec.function:
        artifact_spec = ArtifactSpec(table={})
        output_artifact = TableArtifact(dag=dag, artifact_id=output_artifact_id)
    elif spec.check:
        artifact_spec = ArtifactSpec(bool={})
        output_artifact = CheckArtifact(dag=dag, artifact_id=output_artifact_id)
    else:
        raise AqueductError("Operator spec not supported.")

    apply_deltas_to_dag(
        dag,
        deltas=[
            AddOrReplaceOperatorDelta(
                op=Operator(
                    id=operator_id,
                    name=op_name,
                    description=description,
                    spec=spec,
                    inputs=[artifact.id() for artifact in input_artifacts],
                    outputs=[output_artifact_id],
                ),
                output_artifacts=[
                    Artifact(
                        id=output_artifact_id,
                        name=artifact_name_from_op_name(op_name),
                        spec=artifact_spec,
                    )
                ],
            ),
        ],
    )

    return output_artifact


def op(
    name: Optional[Union[str, UserFunction]] = None,
    description: Optional[str] = None,
    file_dependencies: Optional[List[str]] = None,
    reqs_path: Optional[str] = None,
) -> Union[DecoratedFunction, OutputArtifactFunction]:
    """Decorator that converts regular python functions into an operator.

    Calling the decorated function returns a TableArtifact. The decorated function
    can take any number of artifact inputs.

    The requirements.txt file in the current directory is used, if it exists.

    To run the wrapped code locally, without Aqueduct, use the `local` attribute. Eg:
    >>> compute_recommendations.local(customer_profiles, recent_clicks)

    Args:
        name:
            Operator name.
        description:
            A description for the operator.
        file_dependencies:
            A list of relative paths to files that the function needs to access.
            Python classes/methods already imported within the function's file
            need not be included.
        reqs_path:
            A path to file that specifies requirements for this specific operator.

    Examples:
        The op name is inferred from the function name. The description is pulled from the function
        docstring or can be explicitly set in the decorator.

        >>> @op
        ... def compute_recommendations(customer_profiles, recent_clicks):
        ...     return recommendations
        >>> customer_profiles = db.sql("SELECT * from user_profile", db="postgres")
        >>> recent_clicks = db.sql("SELECT * recent_clicks", db="google_analytics/shopping")
        >>> recommendations = compute_recommendations(customer_profiles, recent_clicks)

        `recommendations` is a TableArtifact representing the result of `compute_recommendations()`.

        >>> recommendations.get()
    """

    def inner_decorator(func: UserFunction) -> OutputArtifactFunction:
        nonlocal name
        nonlocal description
        if callable(name) or name is None:
            name = func.__name__
        if description is None:
            description = func.__doc__ or ""

        def wrapped(*sql_artifacts: TableArtifact) -> TableArtifact:
            """
            Creates the following files in the zipped folder structure:
             - model.py
             - model.pkl
             - requirements.txt
             - python_version.txt
             - <any file dependencies>
            """
            assert isinstance(name, str)
            zip_file = serialize_function(func, file_dependencies, reqs_path)
            function_spec = FunctionSpec(
                type=FunctionType.FILE,
                granularity=FunctionGranularity.TABLE,
                file=zip_file,
            )
            new_function_artifact = wrap_spec(
                OperatorSpec(function=function_spec),
                *sql_artifacts,
                op_name=name,
            )

            assert isinstance(new_function_artifact, TableArtifact)

            return new_function_artifact

        # Enable the .local(*args) attribute, which calls the original function with the raw inputs.
        def local_func(*inputs: InputArtifactLocal) -> DataFrame:
            raw_inputs = [elem.get() if _is_input_artifact(elem) else elem for elem in inputs]
            return func(*raw_inputs)

        setattr(wrapped, "local", local_func)
        return wrapped

    if callable(name):
        return inner_decorator(name)
    else:
        return inner_decorator


def metric(
    name: Optional[Union[str, MetricFunction]] = None,
    description: Optional[str] = None,
) -> Union[DecoratedMetricFunction, OutputArtifactFunction]:
    """Decorator that converts regular python functions into a metric.

    Calling the decorated function returns a MetricArtifact. The decorated function
    can take any number of artifact inputs.

    The requirements.txt file in the current directory is used, if it exists.

    To run the wrapped code locally, without Aqueduct, use the `local` attribute. Eg:
    >>> compute_recommendations.local(customer_profiles, recent_clicks)

    Args:
        name:
            Operator name.
        description:
            A description for the metric.

    Examples:
        The metric name is inferred from the function name. The description is pulled from the function
        docstring or can be explicitly set in the decorator.

        >>> @metric()
        ... def avg_churn(churn_table):
        ...     return churn_table['pred_churn'].mean()
        >>> churn_table = db.sql("SELECT * from churn_table")
        >>> churn_metric = avg_churn(churn_table)

        `churn_metric` is a MetricArtifact representing the result of `avg_churn()`.

        >>> churn_metric.get()
    """

    def inner_decorator(func: MetricFunction) -> OutputArtifactFunction:
        nonlocal name
        nonlocal description
        if callable(name) or name is None:
            name = func.__name__
        if description is None:
            description = func.__doc__ or ""
        """
        @wraps(...): updates `wrapped()` to look like `func()` by copying attributes (eg. __name__, __doc__, etc.)
        """

        @wraps(func)
        def wrapped(
            *artifacts: InputArtifact,
        ) -> MetricArtifact:
            """
            Creates the following files in the zipped folder structure:
             - model.py
             - model.pkl
             - requirements.txt
             - python_version.txt
             - <any file dependencies>
            """
            assert isinstance(name, str)
            assert isinstance(description, str)
            zip_file = serialize_function(func)

            # TODO(ENG-735): Support granularity=FunctionGranularity.TABLE & granularity=FunctionGranularity.ROW
            function_spec = FunctionSpec(
                type=FunctionType.FILE,  # TODO(ENG-811): Support type=FunctionType.GITHUB
                granularity=FunctionGranularity.TABLE,
                file=zip_file,
            )

            metric_spec = MetricSpec(function=function_spec)

            new_metric_artifact = wrap_spec(
                OperatorSpec(metric=metric_spec),
                *artifacts,
                op_name=name,
                description=description,
            )

            assert isinstance(new_metric_artifact, MetricArtifact)

            return new_metric_artifact

        # Enable the .local(*args) attribute, which calls the original function with the raw inputs.
        def local_func(*inputs: InputArtifactLocal) -> float:
            raw_inputs = [elem.get() if _is_input_artifact(elem) else elem for elem in inputs]
            return func(*raw_inputs)

        setattr(wrapped, "local", local_func)
        return wrapped

    if callable(name):
        return inner_decorator(name)
    else:
        return inner_decorator


def check(
    name: Optional[Union[str, CheckFunction]] = None,
    description: Optional[str] = None,
    severity: CheckSeverity = CheckSeverity.WARNING,
) -> Union[DecoratedCheckFunction, OutputArtifactFunction]:
    """Decorator that converts a regular python function into a check.

    Calling the decorated function returns a CheckArtifact. The decorated python function
    can have any number of artifact inputs.

    The requirements.txt file in the current directory is used, if it exists.

    A check can be set with either WARNING or ERROR severity. A failing check with ERROR severity
    will fail the workflow when run in our system.

    To run the wrapped code locally, without Aqueduct, use the `local` attribute. Eg:
    >>> compute_recommendations.local(customer_profiles, recent_clicks)

    Args:
        name:
            Operator name.
        description:
            A description for the check.
        severity:
            The severity level of the check if it fails.

    Examples:
        The check name is inferred from the function name. The description is pulled from the function
        docstring or can be explicitly set in the decorator.

        >>> @check(
        ... description="The average predicted churn is below 0.1",
        ... severity=CheckSeverity.ERROR,
        ... )
        ... def avg_churn_is_low(churn_table):
        ...     return churn_table['pred_churn'].mean() < 0.1
        >>> churn_is_low_check = avg_churn_is_low(churn_table_artifact)

        `churn_is_low_check` is a CheckArtifact representing the result of `avg_churn_is_low()`.

        >>> churn_is_low_check.get()
    """

    def inner_decorator(func: CheckFunction) -> OutputArtifactFunction:
        nonlocal name
        nonlocal description
        if callable(name) or name is None:
            name = func.__name__
        if description is None:
            description = func.__doc__ or ""
        """
        @wraps(...): updates `wrapped()` to look like `func()` by copying attributes (eg. __name__, __doc__, etc.)
        """

        @wraps(func)
        def wrapped(
            *artifacts: InputArtifact,
        ) -> CheckArtifact:
            """
            Creates the following files in the zipped folder structure:
             - model.py
             - model.pkl
             - requirements.txt
             - python_version.txt
             - <any file dependencies>
            """
            assert isinstance(name, str)
            assert isinstance(description, str)
            zip_file = serialize_function(func)
            function_spec = FunctionSpec(
                type=FunctionType.FILE,
                granularity=FunctionGranularity.TABLE,
                file=zip_file,
            )
            check_spec = CheckSpec(level=severity, function=function_spec)

            new_check_artifact = wrap_spec(
                OperatorSpec(check=check_spec),
                *artifacts,
                op_name=name,
                description=description,
            )

            assert isinstance(new_check_artifact, CheckArtifact)

            return new_check_artifact

        # Enable the .local(*args) attribute, which calls the original function with the raw inputs.
        def local_func(*inputs: InputArtifactLocal) -> bool:
            raw_inputs = [elem.get() if _is_input_artifact(elem) else elem for elem in inputs]
            return func(*raw_inputs)

        setattr(wrapped, "local", local_func)
        return wrapped

    if callable(name):
        return inner_decorator(name)
    else:
        return inner_decorator
