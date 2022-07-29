import copy
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from aqueduct.artifact import Artifact, get_artifact_type
from aqueduct.enums import ArtifactType, OperatorType, TriggerType
from aqueduct.error import (
    ArtifactNotFoundException,
    InternalAqueductError,
    InvalidUserActionException,
    InvalidUserArgumentException,
)
from aqueduct.operators import (
    Operator,
    OperatorSpec,
    ParamSpec,
    get_operator_type,
    get_operator_type_from_spec,
    serialize_parameter_value,
)
from pydantic import BaseModel


class Schedule(BaseModel):
    trigger: Optional[TriggerType] = None
    cron_schedule: str = ""
    disable_manual_trigger: bool = False


class RetentionPolicy(BaseModel):
    k_latest_runs: int = -1


class Metadata(BaseModel):
    """These fields should always set when writing/reading from the backend."""

    name: Optional[str]
    description: Optional[str]
    schedule: Optional[Schedule]
    retention_policy: Optional[RetentionPolicy]


class DAG(BaseModel):
    operators: Dict[str, Operator] = {}
    artifacts: Dict[str, Artifact] = {}

    # Allows for quick operator lookup by name.
    # Is excluded from json serialization.
    operator_by_name: Dict[str, Operator] = {}

    # These fields must be set when publishing the workflow
    metadata: Metadata

    class Config:
        fields = {
            "operators_by_name": {"exclude": ...},
        }

    def must_get_operator(
        self,
        with_id: Optional[uuid.UUID] = None,
        with_name: Optional[str] = None,
        with_output_artifact_id: Optional[uuid.UUID] = None,
    ) -> Operator:
        op = self.get_operator(with_id, with_name, with_output_artifact_id)
        if op is None:
            raise InternalAqueductError(
                "Unable to find operator: with_id %s, with_name %s, with_output_artifact_id %s"
                % (str(with_id), with_name, str(with_output_artifact_id)),
            )
        return op

    def get_operator(
        self,
        with_id: Optional[uuid.UUID] = None,
        with_name: Optional[str] = None,
        with_output_artifact_id: Optional[uuid.UUID] = None,
    ) -> Optional[Operator]:
        if (
            int(with_id is not None)
            + int(with_name is not None)
            + int(with_output_artifact_id is not None)
        ) != 1:
            raise InternalAqueductError(
                "Cannot fetch operator with multiple search parameters set."
            )

        if with_id is not None:
            return self.operators.get(str(with_id))

        elif with_name is not None:
            return self.operator_by_name.get(with_name)

        # Search with output artifact id
        for _, op in self.operators.items():
            if with_output_artifact_id in op.outputs:
                return op
        return None

    def list_operators(
        self,
        filter_to: Optional[List[OperatorType]] = None,
        on_artifact_id: Optional[uuid.UUID] = None,
    ) -> List[Operator]:
        """Multiple conditions can be applied to filter down the list of operators."""
        operators = list(self.operators.values())

        if filter_to is not None:
            operators = [op for op in operators if get_operator_type(op) in filter_to]

        if on_artifact_id is not None:
            operators = [op for op in operators if on_artifact_id in op.inputs]
        return operators

    def list_downstream_operators(
        self,
        op_id: uuid.UUID,
    ) -> List[uuid.UUID]:
        """Returns a list of all operators that depend on the given operator. Includes the given operator."""
        downstream_ops = []

        q = [op_id]
        seen_op_ids = set(q)
        while len(q) > 0:
            curr_op_id = q.pop(0)
            downstream_ops.append(curr_op_id)

            curr_op = self.must_get_operator(with_id=curr_op_id)
            for output_artifact_id in curr_op.outputs:
                next_op_ids = [
                    op.id
                    for op in self.list_operators(on_artifact_id=output_artifact_id)
                    if op.id not in seen_op_ids
                ]
                seen_op_ids.union(set(next_op_ids))
                q.extend(next_op_ids)

        return downstream_ops

    def list_root_operators(
        self, for_artifact_ids: Optional[List[uuid.UUID]] = None
    ) -> List[Operator]:
        all_root_operators = [op for op in self.operators.values() if len(op.inputs) == 0]
        if for_artifact_ids is None:
            return all_root_operators

        # Perform a DFS in the reverse direction to find all upstream operators, starting at the given artifacts.
        root_operators = []
        q: List[Operator] = [
            self.must_get_operator(with_output_artifact_id=artifact_id)
            for artifact_id in for_artifact_ids
        ]
        seen_op_ids = set(op.id for op in q)
        while len(q):
            curr_op = q.pop(0)
            if get_operator_type(curr_op) == OperatorType.EXTRACT:
                root_operators.append(curr_op)
                continue

            input_operators = [
                self.must_get_operator(with_output_artifact_id=input_artifact_id)
                for input_artifact_id in curr_op.inputs
            ]
            previous_operators = [op for op in input_operators if op.id not in seen_op_ids]
            q.extend(previous_operators)
            seen_op_ids.union(set(op.id for op in previous_operators))

        return root_operators

    def must_get_artifact(self, artifact_id: uuid.UUID) -> Artifact:
        if str(artifact_id) not in self.artifacts:
            raise ArtifactNotFoundException("Unable to find artifact.")
        return self.artifacts[str(artifact_id)]

    def must_get_artifacts(self, artifact_ids: List[uuid.UUID]) -> List[Artifact]:
        return [self.must_get_artifact(artifact_id) for artifact_id in artifact_ids]

    def get_artifacts_by_name(self, name: str) -> Optional[Artifact]:
        for artifact in self.list_artifacts():
            if artifact.name == name:
                return artifact

        return None

    def list_artifacts(
        self,
        on_op_ids: Optional[List[uuid.UUID]] = None,
        filter_to: Optional[List[ArtifactType]] = None,
    ) -> List[Artifact]:
        """Returns all artifacts in the DAG with the following optional filters:

        Args:
            `on_op_ids`: only artifacts that are the outputs of these operators are included.
        """
        artifacts = [artifact for artifact in self.artifacts.values()]

        if on_op_ids is not None:
            operators = [self.must_get_operator(op_id) for op_id in on_op_ids]
            artifact_ids = set()
            for op in operators:
                artifact_ids.update(op.outputs)
            artifacts = self.must_get_artifacts(list(artifact_ids))

        if filter_to is not None:
            artifacts = [
                artifact for artifact in artifacts if get_artifact_type(artifact) in filter_to
            ]

        return artifacts

    ######################## DAG WRITES #############################

    def add_operator(self, op: Operator) -> None:
        self.add_operators([op])

    def add_operators(self, ops: List[Operator]) -> None:
        for op in ops:
            self.operators[str(op.id)] = op
            self.operator_by_name[op.name] = op

    def add_artifacts(self, artifacts: List[Artifact]) -> None:
        for artifact in artifacts:
            self.artifacts[str(artifact.id)] = artifact

    def update_operator_spec(self, name: str, spec: OperatorSpec) -> None:
        """Replaces an operator's spec in the dag.

        The assumption validated within the method is that the caller has already validated
        both that the operator exists, and that the spec type will be unchanged.
        """
        assert name in self.operator_by_name, "Operator %s does not exist." % name
        op = self.operator_by_name[name]
        assert get_operator_type(op) == get_operator_type_from_spec(
            spec
        ), "New spec has a different type."

        self.operators[str(op.id)].spec = spec
        self.operator_by_name[op.name].spec = spec

    def update_operator_function(self, operator: Operator, serialized_function: bytes) -> None:
        if operator in self.operators.values():
            operator.update_serialized_function(serialized_function)

    def remove_operator(
        self,
        operator_id: uuid.UUID,
        must_be_type: Optional[OperatorType] = None,
    ) -> None:
        """Deletes the given operator from the DAG, along with any direct output artifacts.

        Args:
            operator_id:
                The operator to delete (and to start deletion at)
            must_be_type:
                If set, will only delete the given operator if it is of the same operator type.
        """
        self.remove_operators([operator_id], must_be_type)

    def remove_operators(
        self,
        operator_ids: List[uuid.UUID],
        must_be_type: Optional[OperatorType] = None,
    ) -> None:
        """Batch version of `remove_operator()`."""
        for operator_id in operator_ids:
            op_to_remove = self.operators[str(operator_id)]
            if must_be_type is not None and get_operator_type(op_to_remove) != must_be_type:
                raise InternalAqueductError(
                    "Cannot remove operator of type %s, must be of type %s."
                    % (get_operator_type(op_to_remove), must_be_type)
                )

            for artifact_id in op_to_remove.outputs:
                del self.artifacts[str(artifact_id)]
            del self.operators[str(op_to_remove.id)]
            del self.operator_by_name[op_to_remove.name]


class DAGDelta(ABC):
    """Abstract class for the various types of DAG updates."""

    @abstractmethod
    def apply(self, dag: DAG) -> None:
        pass


class AddOrReplaceOperatorDelta(DAGDelta):
    """Adds an operator and its output artifacts to the DAG.

    If the operator name already exists in the dag, we will remove the old, colliding
    operator, along with all its downstream dependencies before adding the operator.

    Attributes:
        op:
            The new operator to add.
        output_artifacts:
            The output artifacts for this operation.
    """

    def __init__(self, op: Operator, output_artifacts: List[Artifact]):
        # Check that the operator's outputs correspond to the given output artifacts.
        if len(op.outputs) != len(output_artifacts):
            raise InternalAqueductError(
                "Number of operator outputs does not match number of given artifacts."
            )

        for i, artifact_id in enumerate(op.outputs):
            if output_artifacts[i].id != artifact_id:
                raise InternalAqueductError(
                    "The %dth output artifact on the operator does not match." % i
                )

        self.op = op
        self.output_artifacts = output_artifacts

    def apply(self, dag: DAG) -> None:
        # If there exists an operator with the same name, remove it and its dependencies first!
        colliding_op = dag.get_operator(with_name=self.op.name)
        if colliding_op is not None:
            if get_operator_type(self.op) != get_operator_type(colliding_op):
                raise InvalidUserActionException(
                    "Another operator exists with the same name %s, but is of a different type %s."
                    % (self.op.name, get_operator_type(self.op)),
                )

            # The colliding operator cannot be an dependency of the new operator. Otherwise, we would
            # not be able to remove the colliding operator.
            downstream_op_ids = dag.list_downstream_operators(colliding_op.id)
            for op_id in downstream_op_ids:
                downstream_op = dag.must_get_operator(op_id)
                if len(set(downstream_op.outputs).intersection(set(self.op.inputs))) > 0:
                    raise InvalidUserActionException(
                        "Another operator exists with the same name %s, but cannot be overwritten "
                        "because it is a dependency of the new operator." % self.op.name,
                    )

            print(
                "Warning: You are overwriting the previously defined operator `%s`. Any downstream "
                "artifacts of that operator will need to be recomputed and re-saved." % self.op.name
            )
            for op_id in downstream_op_ids:
                dag.remove_operator(op_id)

        dag.add_operator(self.op)
        dag.add_artifacts(self.output_artifacts)


class SubgraphDAGDelta(DAGDelta):
    """
    Computes a valid subgraph of the given DAG, where every terminal artifact or
    operator must have been explicitly requested.

    Attributes:
        artifact_ids:
            These artifacts describe what our returned subgraph will look like:
            only these artifacts can be terminal nodes.
        include_load_operators:
            Whether to include all load operators on all artifacts in the subgraph.
        include_check_artifacts:
            Whether to include all check operators on all artifacts in the subgraph.
            This means all dependencies of such checks will be included, even if they
            were not part of the original subgraph. If false, all check operators not
            explicitly defined in `artifact_ids` will be excluded.
    """

    def __init__(
        self,
        artifact_ids: Optional[List[uuid.UUID]] = None,
        include_load_operators: bool = False,
        include_check_artifacts: bool = False,
    ):
        if artifact_ids is None or len(artifact_ids) == 0:
            raise InternalAqueductError("Must set artifact ids when pruning dag.")

        self.artifact_ids: List[uuid.UUID] = [] if artifact_ids is None else artifact_ids
        self.include_load_operators = include_load_operators
        self.include_check_artifacts = include_check_artifacts

    def apply(self, dag: DAG) -> None:
        # Check that all the artifact ids exist in the dag.
        for artifact_id in self.artifact_ids:
            _ = dag.must_get_artifact(artifact_id)

        # Starting at the terminal artifacts, perform a DFS in the reverse direction to find
        # all upstream artifacts.
        upstream_artifact_ids = set()
        load_operator_ids = []

        q: List[uuid.UUID] = copy.copy(self.artifact_ids)
        seen_artifact_ids = set(q)
        while len(q) > 0:
            curr_artifact_id = q.pop(0)

            # Keep the extract/function operators along the path.
            upstream_artifact_ids.add(curr_artifact_id)

            # If requested, keep load operators on all artifacts along the way.
            if self.include_load_operators:
                load_ops = dag.list_operators(
                    filter_to=[OperatorType.LOAD], on_artifact_id=curr_artifact_id
                )
                load_operator_ids.extend([op.id for op in load_ops])

            # The operator who's output is the current artifact.
            curr_op = dag.must_get_operator(with_output_artifact_id=curr_artifact_id)
            candidate_next_artifact_ids = copy.copy(curr_op.inputs)

            # If we need to include checks, also include those in future searches
            # (since they may have their own dependencies)
            if self.include_check_artifacts:
                check_ops = dag.list_operators(
                    on_artifact_id=curr_artifact_id, filter_to=[OperatorType.CHECK]
                )
                check_artifacts = dag.list_artifacts(on_op_ids=[op.id for op in check_ops])
                candidate_next_artifact_ids.extend([artifact.id for artifact in check_artifacts])

            # Prune the upstream candidates against our "already seen" group.
            next_artifact_ids = set(candidate_next_artifact_ids).difference(seen_artifact_ids)

            # Update the queue and seen groups.
            q.extend(next_artifact_ids)
            seen_artifact_ids.update(next_artifact_ids)

        # Remove all operators and artifacts not in the upstream DAG we computed above.
        all_op_ids = set(op.id for op in dag.list_operators())
        upstream_ops = [
            dag.must_get_operator(with_output_artifact_id=artifact_id)
            for artifact_id in upstream_artifact_ids
        ]
        upstream_op_ids = [op.id for op in upstream_ops] + load_operator_ids
        dag.remove_operators(list(all_op_ids.difference(upstream_op_ids)))


class RemoveCheckOperatorDelta(DAGDelta):
    """Removes the check operator on the given artifact that has the given name.

    Raises:
        InvalidUserActionException: if a matching check operator could not be found.
    """

    def __init__(
        self,
        check_name: str,
        artifact_id: uuid.UUID,
    ):
        self.check_name = check_name
        self.artifact_id = artifact_id

    def apply(self, dag: DAG) -> None:
        check_ops = dag.list_operators(
            filter_to=[OperatorType.CHECK], on_artifact_id=self.artifact_id
        )
        check_names_for_op = [op.name for op in check_ops]

        assert len(set(check_names_for_op)) == len(
            check_names_for_op
        ), "Check operator names must be unique."

        found: bool = False
        for i, name in enumerate(check_names_for_op):
            if name == self.check_name:
                found = True
                dag.remove_operator(operator_id=check_ops[i].id, must_be_type=OperatorType.CHECK)

        if not found:
            raise InvalidUserActionException(
                "No check with name %s exists on artifact!" % self.check_name
            )


def validate_overwriting_parameters(dag: DAG, parameters: Dict[str, Any]) -> None:
    """Validates any parameters the user supplies that override the default value.

    The following checks are performed:
    - every parameter corresponds to a parameter artifact in the dag.
    - every parameter name is a string.
    - any parameter feeding into a sql query must have a string value (to resolve tags within the query).

    Raises:
        InvalidUserArgumentException:
            If any of the above checks are violated.
    """
    if any(not isinstance(name, str) for name in parameters):
        raise InvalidUserArgumentException("Parameters must be keyed by strings.")

    for param_name, param_val in parameters.items():
        param_op = dag.get_operator(with_name=param_name)
        if param_op is None:
            raise InvalidUserArgumentException(
                "Parameter %s cannot be found, or is not utilized in the current computation."
                % param_name
            )
        if get_operator_type(param_op) != OperatorType.PARAM:
            raise InvalidUserArgumentException(
                "Parameter %s must refer to a parameter, but instead refers to a: %s"
                % (param_name, get_operator_type(param_op))
            )

        # Any parameter that is consumed by a SQL operator must be a string type!
        assert len(param_op.outputs) == 1
        param_artifact_id = param_op.outputs[0]
        ops_on_param = dag.list_operators(on_artifact_id=param_artifact_id)
        if any(get_operator_type(op) == OperatorType.EXTRACT for op in ops_on_param):
            if not isinstance(param_val, str):
                raise InvalidUserArgumentException(
                    "Parameter %s is used by a sql query, so it must be a string type, not type %s."
                    % (param_name, type(param_val).__name__)
                )


class UpdateParametersDelta(DAGDelta):
    """Updates the values of the given parameters in the DAG to the given values. No-ops if no parameters provided."""

    def __init__(
        self,
        parameters: Optional[Dict[str, Any]],
    ):
        self.parameters = parameters

    def apply(self, dag: DAG) -> None:
        if self.parameters is None:
            return
        validate_overwriting_parameters(dag, self.parameters)

        for param_name, new_val in self.parameters.items():
            dag.update_operator_spec(
                param_name,
                OperatorSpec(
                    param=ParamSpec(
                        val=serialize_parameter_value(param_name, self.parameters[param_name])
                    )
                ),
            )


def apply_deltas_to_dag(dag: DAG, deltas: List[DAGDelta], make_copy: bool = False) -> DAG:
    if make_copy:
        dag = copy.deepcopy(dag)

    for delta in deltas:
        delta.apply(dag)

    return dag


# Initialize a module-level dag object, to be accessed and modified when the user construct the flow.
__GLOBAL_DAG__ = DAG(metadata=Metadata())
