from __future__ import annotations

import json
import uuid
from typing import Any, Callable, Dict, List, Optional

from aqueduct.artifact import ArtifactSpec
from aqueduct.check_artifact import CheckArtifact
from aqueduct.dag import (
    DAG,
    AddOrReplaceOperatorDelta,
    RemoveCheckOperatorDelta,
    SubgraphDAGDelta,
    UpdateParametersDelta,
    apply_deltas_to_dag,
)
from aqueduct.enums import CheckSeverity, FunctionGranularity, FunctionType
from aqueduct.error import AqueductError
from aqueduct.generic_artifact import Artifact
from aqueduct.operators import CheckSpec, FunctionSpec, Operator, OperatorSpec
from aqueduct.utils import (
    artifact_name_from_op_name,
    format_header_for_print,
    generate_uuid,
    get_description_for_metric,
    serialize_function,
)

import aqueduct
from aqueduct import api_client


class MetricArtifact(Artifact):
    """This class represents a computed metric within the flow's DAG.

    Any `@metric`-annotated python function that returns a float will
    return this class when that function is called.

    Examples:
        >>> @metric
        >>> def compute_metric(df):
        >>>     return metric
        >>> metric_artifact = compute_metric(input_artifact)

        The contents of this artifact can be manifested locally.

        >>> val = metric_artifact.get()
    """

    def __init__(self, dag: DAG, artifact_id: uuid.UUID, from_flow_run: bool = False):
        self._dag = dag
        self._artifact_id = artifact_id
        # This parameter indicates whether the artifact is fetched from flow-run or not.
        self._from_flow_run = from_flow_run

    def get(self, parameters: Optional[Dict[str, Any]] = None) -> float:
        """Materializes a MetricArtifact into its immediate float value.

        Returns:
            The evaluated metric as a float.

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

        if artifact_result.metric:
            # Return the metric float.
            return artifact_result.metric.val
        else:
            raise AqueductError("Unable to parse execution results.")

    BOUND_LOWER = "bound"
    BOUND_UPPER = "upper"
    BOUND_EQUAL = "equal"
    BOUND_NOTEQUAL = "notequal"

    def list_preset_checks(self) -> List[str]:
        """Returns a list of all preset checks available on the metric artifact.
        These preset checks can be set via the bound() method on a artifact.

        Returns:
            A list of available preset checks on a metric
        """
        return [self.BOUND_LOWER, self.BOUND_UPPER, self.BOUND_EQUAL, self.BOUND_NOTEQUAL]

    def bound(
        self,
        upper: Optional[float] = None,
        lower: Optional[float] = None,
        equal: Optional[float] = None,
        notequal: Optional[float] = None,
        severity: CheckSeverity = CheckSeverity.WARNING,
    ) -> CheckArtifact:
        """Computes a bounds check on this metric with the specified boundary condition.

        Only one of `upper` and `lower` can be set.

        >>> metric_artifact.bound(upper = 0.9, severity = CheckSeverity.Error)

        If the metric ever exceeds 0.9, the flow will fail.

        Args:
            upper:
                Sets an upper bound on the value of the metric.
            lower:
                Sets a lower bound on the value of the metric.
            severity:
                If specified, will set the severity of this check as specified. Defaults to CheckSeverity.WARNING

        Returns:
            A check artifact bound to this metric.
        """
        input_mapping = {
            self.BOUND_UPPER: upper,
            self.BOUND_LOWER: lower,
            self.BOUND_EQUAL: equal,
            self.BOUND_NOTEQUAL: notequal,
        }

        param_found = False
        for param, value in input_mapping.items():
            if value is None:
                continue
            if param_found:
                raise AqueductError(
                    "Can only support one parameter to bound metric too. Multiple provided: %s, %s"
                    % (bound_name, param)
                )

            param_found = True
            bound_name: str = param
            bound_value = value

        if not param_found:
            raise AqueductError(
                "Could not find a parameter for bounding the metric please specify one of either: %s"
                % (",".join(input_mapping.keys()))
            )

        assert bound_name and bound_value

        accepted_types = [float, int]
        if type(bound_value) not in accepted_types:
            raise AqueductError(
                "Value for bound '%s' must be one of %s type, found %s"
                % (
                    bound_name,
                    accepted_types,
                    type(bound_value),
                )
            )

        metric_name = self._dag.must_get_operator(with_output_artifact_id=self._artifact_id).name

        if bound_name is self.BOUND_LOWER:
            name = "greater than %s" % bound_value
            description = "Check that the metric %s is greater than %s" % (metric_name, bound_value)

            def check_lower_bound(metric_val: float) -> bool:
                return metric_val > bound_value

            bound_fn = check_lower_bound
        elif bound_name is self.BOUND_UPPER:
            name = "less than %s" % bound_value
            description = "Check that the metric %s is less than %s" % (metric_name, bound_value)

            def check_upper_bound(metric_val: float) -> bool:
                return metric_val < bound_value

            bound_fn = check_upper_bound
        elif bound_name is self.BOUND_EQUAL:
            name = "equal to %s" % bound_value
            description = "Check that the metric %s is equal too %s" % (metric_name, bound_value)

            def check_equal_bound(metric_val: float) -> bool:
                return metric_val == bound_value

            bound_fn = check_equal_bound
        else:
            name = "not equal to %s" % bound_value
            description = "Check that the metric %s is not equal too %s" % (
                metric_name,
                bound_value,
            )

            def check_not_equal_bound(metric_val: float) -> bool:
                return metric_val != bound_value

            bound_fn = check_not_equal_bound

        return self.__apply_bound_fn_to_metric(bound_fn, name, description, severity)

    def __apply_bound_fn_to_metric(
        self,
        check_function: Callable[..., bool],
        check_name: str,
        check_description: str,
        severity: CheckSeverity = CheckSeverity.WARNING,
    ) -> CheckArtifact:
        zip_file = serialize_function(check_function)
        function_spec = FunctionSpec(
            type=FunctionType.FILE,
            granularity=FunctionGranularity.TABLE,
            file=zip_file,
        )
        op_spec = OperatorSpec(check=CheckSpec(level=severity, function=function_spec))

        operator_id = generate_uuid()
        output_artifact_id = generate_uuid()
        apply_deltas_to_dag(
            self._dag,
            deltas=[
                AddOrReplaceOperatorDelta(
                    op=Operator(
                        id=operator_id,
                        name=check_name,
                        description=check_description,
                        spec=op_spec,
                        inputs=[self._artifact_id],
                        outputs=[output_artifact_id],
                    ),
                    output_artifacts=[
                        aqueduct.artifact.Artifact(
                            id=output_artifact_id,
                            name=artifact_name_from_op_name(check_name),
                            spec=ArtifactSpec(bool={}),
                        )
                    ],
                ),
            ],
        )

        return CheckArtifact(dag=self._dag, artifact_id=output_artifact_id)

    def remove_check(self, name: str) -> None:
        apply_deltas_to_dag(
            self._dag,
            deltas=[
                RemoveCheckOperatorDelta(check_name=name, artifact_id=self._artifact_id),
            ],
        )

    def _describe(self) -> Dict[str, Any]:
        input_operator = self._dag.must_get_operator(with_output_artifact_id=self._artifact_id)

        general_dict = get_description_for_metric(input_operator, self._dag)

        # Remove because values already in `readable_dict`
        general_dict.pop("Label")
        general_dict.pop("Granularity")

        readable_dict = super()._describe()
        readable_dict.update(general_dict)
        readable_dict["Inputs"] = [
            self._dag.must_get_artifact(artf).name for artf in input_operator.inputs
        ]

        return readable_dict

    def describe(self) -> None:
        """Prints out a human-readable description of the metric artifact."""
        input_operator = self._dag.must_get_operator(with_output_artifact_id=self._artifact_id)
        print(format_header_for_print(f"'{input_operator.name}' Metric Artifact"))
        print(json.dumps(self._describe(), sort_keys=False, indent=4))
