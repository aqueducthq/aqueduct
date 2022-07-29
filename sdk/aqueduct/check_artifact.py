from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from aqueduct.dag import DAG, SubgraphDAGDelta, UpdateParametersDelta, apply_deltas_to_dag
from aqueduct.error import AqueductError
from aqueduct.generic_artifact import Artifact
from aqueduct.utils import format_header_for_print, get_description_for_check

from aqueduct import api_client


class CheckArtifact(Artifact):
    """This class represents a check within the flow's DAG.

    Any `@check`-annotated python function that returns a boolean will
    return this class when that function is called called. This also
    is returned from pre-defined functions like metric.bound(...).

    Examples:
        >>> @check
        >>> def check_something(df1, metric) -> bool:
        >>> return check_result
        >>>
        >>> check_artifact = check_something(table_artifact, metric_artifact)

        The contents of the check artifact can be manifested locally:

        >>> assert check_artifact.get()
    """

    def __init__(self, dag: DAG, artifact_id: uuid.UUID, from_flow_run: bool = False):
        self._dag = dag
        self._artifact_id = artifact_id
        # This parameter indicates whether the artifact is fetched from flow-run or not.
        self._from_flow_run = from_flow_run

    def get(self, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """Materializes a CheckArtifact into a boolean.

        Returns:
            A boolean representing whether the check passed or not.

        Raises:
            InvalidRequestError:
                An error occurred because of an issue with the user's code or inputs.
            InternalServerError:
                An unexpected error occurred in the server.
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

        if artifact_result.check:
            return artifact_result.check.passed
        else:
            raise AqueductError("Unable to parse execution results.")

    def describe(self) -> None:
        """Prints out a human-readable description of the check artifact."""
        input_operator = self._dag.must_get_operator(with_output_artifact_id=self._artifact_id)

        general_dict = get_description_for_check(input_operator)

        # Remove because values already in `readable_dict`
        general_dict.pop("Label")
        general_dict.pop("Level")

        readable_dict = super()._describe()
        readable_dict.update(general_dict)
        readable_dict["Inputs"] = [
            self._dag.must_get_artifact(artf).name for artf in input_operator.inputs
        ]

        print(format_header_for_print(f"'{input_operator.name}' Check Artifact"))
        print(json.dumps(readable_dict, sort_keys=False, indent=4))
