import json
import textwrap
import uuid
from typing import Any, Dict, Optional

from aqueduct.dag import DAG
from aqueduct.error import InvalidUserArgumentException
from aqueduct.generic_artifact import Artifact
from aqueduct.utils import format_header_for_print


class ParamArtifact(Artifact):
    def __init__(self, dag: DAG, artifact_id: uuid.UUID, from_flow_run: bool = False):
        """The APIClient is only included because decorated functions operators acting on this parameter
        will need a handle to an API client."""
        self._dag = dag
        self._artifact_id = artifact_id
        # This parameter indicates whether the artifact is fetched from flow-run or not.
        self._from_flow_run = from_flow_run

    def get(self, parameters: Optional[Dict[str, Any]] = None) -> Any:
        if parameters is not None:
            raise InvalidUserArgumentException(
                "Parameters cannot be supplied to parameter artifacts."
            )

        _ = self._dag.must_get_artifact(self._artifact_id)
        param_op = self._dag.must_get_operator(with_output_artifact_id=self._artifact_id)
        assert param_op.spec.param is not None, "Artifact is not a parameter."
        return json.loads(param_op.spec.param.val)

    def describe(self) -> None:
        print(
            textwrap.dedent(
                f"""
            {format_header_for_print(f"'{self.name()}' Parameter")}
            Value: {self.get()}
            """
            )
        )
