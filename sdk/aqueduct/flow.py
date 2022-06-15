import json
import uuid
from .artifact import Artifact
from aqueduct.check_artifact import CheckArtifact
from aqueduct.metric_artifact import MetricArtifact

from typing import Dict, List, Mapping, Union, Any
from textwrap import wrap

from aqueduct.integrations.integration import IntegrationInfo

import plotly.graph_objects as go
from aqueduct.api_client import APIClient
from aqueduct.dag import DAG, construct_dag
from aqueduct.error import ArtifactNotFoundException, AqueductError, InvalidUserArgumentException
from aqueduct.table_artifact import TableArtifact
from aqueduct.enums import DisplayNodeType, OperatorType
from .flow_run import FlowRun
from .operators import Operator
from .responses import GetWorkflowResponse, WorkflowDagResultResponse, WorkflowDagResponse
from .utils import parse_user_supplied_id


class Flow:
    """This class is a read-only handle to a workflow that in the system.

    A flow can have multiple runs within it.
    """

    def __init__(
        self,
        api_client: APIClient,
        flow_id: str,
        in_notebook_or_console_context: bool,
    ):
        assert flow_id is not None
        self._api_client = api_client
        self._id = flow_id
        self._in_notebook_or_console_context = in_notebook_or_console_context

    def id(self) -> uuid.UUID:
        """Returns the id of the flow."""
        return uuid.UUID(self._id)

    def list_runs(self) -> List[Dict[str, str]]:
        # TODO: docstring (note that this is in reverse order)
        resp = self._api_client.get_workflow(self._id)
        return [
            dag_result.to_readable_dict()
            for dag_result in reversed(resp.workflow_dag_results)
        ]

    def _reconstruct_dag(self, workflow_dag: WorkflowDagResponse) -> DAG:
        return DAG(
            operators=workflow_dag.operators,
            artifacts=workflow_dag.artifacts,
            operator_by_name={
                op.name: op for op in workflow_dag.operators.values()
            },
            metadata=workflow_dag.metadata,
        )

    def latest(self) -> FlowRun:
        resp = self._api_client.get_workflow(self._id)
        assert len(resp.workflow_dag_results) > 0, "Every flow must have at least one run attached to it."

        latest_result = resp.workflow_dag_results[0]
        workflow_dag = resp.workflow_dags[latest_result.workflow_dag_id]
        dag = self._reconstruct_dag(workflow_dag)
        return FlowRun(
            api_client=self._api_client,
            run_id=str(latest_result.id),
            in_notebook_or_console_context=self._in_notebook_or_console_context,
            dag=dag,
        )

    def fetch(self, run_id: Union[str, uuid.UUID]) -> FlowRun:
        run_id = parse_user_supplied_id(run_id)

        resp = self._api_client.get_workflow(self._id)
        assert len(resp.workflow_dag_results) > 0, "Every flow must have at least one run attached to it."

        result = None
        for candidate_result in resp.workflow_dag_results:
            if str(candidate_result.id) == run_id:
                assert result is None, "Cannot have two runs with the same id."
                result = candidate_result

        if result is None:
            raise InvalidUserArgumentException("Cannot find any run with id %s on this flow." % run_id)

        workflow_dag = resp.workflow_dags[result.workflow_dag_id]
        dag = self._reconstruct_dag(workflow_dag)
        return FlowRun(
            api_client=self._api_client,
            run_id=str(result.id),
            in_notebook_or_console_context=self._in_notebook_or_console_context,
            dag=dag,
        )


    # def describe(self) -> None:
    #     """
    #     Prints out a human-readable description of the flow.
    #
    #     Raises:
    #         ArtifactNotFoundException:
    #             An error occurred because the artifact spec is not a supported type.
    #     """
    #
    #     print("==================== FLOW =================================")
    #     if self._in_notebook_or_console_context:
    #         _show_dag(self._api_client, self._dag)
    #
    #     readable_dict = {
    #         "Flow Name: ": self._dag.metadata.name,
    #         "Flow Description: ": self._dag.metadata.description,
    #     }
    #     print(json.dumps(readable_dict, sort_keys=False, indent=4))
    #
    #     artifacts = self._dag.list_artifacts()
    #     for artifact in artifacts:
    #         if artifact.spec.float != None:
    #             MetricArtifact(
    #                 api_client=self._api_client, dag=self._dag, artifact_id=artifact.id
    #             ).describe()
    #         elif artifact.spec.bool != None:
    #             CheckArtifact(
    #                 api_client=self._api_client, dag=self._dag, artifact_id=artifact.id
    #             ).describe()
    #         elif artifact.spec.table != None:
    #             TableArtifact(
    #                 api_client=self._api_client, dag=self._dag, artifact_id=artifact.id
    #             ).describe()
    #         else:
    #             raise ArtifactNotFoundException(
    #                 "Artifact type not supported. Artifact spec is: %s" % artifact.spec
    #             )


# TODO(ENG-1049): find a better place to put this. It cannot be put in utils.py because of
#  a circular dependency with `api_client.py`. We should move `api_client.py` to an
#  internal directory.
def _show_dag(
    api_client: APIClient,
    dag: DAG,
    label_width: int = 20,
    markersize: int = 50,
    operator_color: str = "#6aa2cc",
    artifact_color: str = "#aecfe8",
) -> None:
    """Show the DAG visually.

    Parameter operators are stripped from the displayed DAG after positions are calculated.

    Args:
        label_width: number of characters per line in detail pop-up.
                     Also equal to 3 + the number of characters to display on graph before truncating.
        markersize: size of each node (width).
        operator_color: color of the operator node.
        artifact_color: color of the artifact node.
    """
    operator_by_id: Dict[str, Operator] = {}
    artifact_by_id: Dict[str, Artifact] = {}
    operator_mapping: Dict[str, Dict[str, Any]] = {}

    for operator in dag.list_operators():
        operator_by_id[str(operator.id)] = operator
        # Convert to strings because the json library cannot serialize UUIDs.
        operator_mapping[str(operator.id)] = {
            "inputs": [str(v) for v in operator.inputs],
            "outputs": [str(v) for v in operator.outputs],
            "name": operator.name,
        }
    for artifact_uuid in dag.list_artifacts():
        artifact_by_id[str(artifact_uuid.id)] = artifact_uuid

    # Mapping of operator/artifact UUID to X, Y coordinates on the graph.
    operator_positions, artifact_positions = api_client.get_node_positions(operator_mapping)

    # Remove any parameter operators, since we don't want those being displayed to the user.
    for param_op in dag.list_operators(filter_to=[OperatorType.PARAM]):
        del operator_positions[str(param_op.id)]

    # Y axis is flipping compared to the UI display, so we negate the Y values so the display matches the UI.
    for positions in [operator_positions, artifact_positions]:
        for node in positions:
            positions[node]["y"] *= -1

    class NodeProperties:
        def __init__(
            self,
            node_type: str,
            positions: Mapping[str, Mapping[str, float]],
            mapping: Union[Mapping[str, Operator], Mapping[str, Artifact]],
            color: str,
        ) -> None:
            self.node_type = node_type
            self.positions = positions
            self.mapping = mapping
            self.color = color

    nodes_properties = [
        NodeProperties(
            DisplayNodeType.OPERATOR, operator_positions, operator_by_id, operator_color
        ),
        NodeProperties(
            DisplayNodeType.ARTIFACT, artifact_positions, artifact_by_id, artifact_color
        ),
    ]

    traces = []

    # Edges
    # Draws the edges connecting each node.
    edge_x: List[Union[float, None]] = []
    edge_y: List[Union[float, None]] = []
    for op_id in operator_positions.keys():
        op_pos = operator_positions[op_id]
        op = dag.must_get_operator(with_id=uuid.UUID(op_id))

        # (x, y) coordinates are at the center of the node.
        for artifact in [*op.outputs, *op.inputs]:
            artf = artifact_positions[str(artifact)]

            edge_x.append(op_pos["x"])
            edge_x.append(artf["x"])
            edge_x.append(None)

            edge_y.append(op_pos["y"])
            edge_y.append(artf["y"])
            edge_y.append(None)

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line={"width": 2, "color": "DarkSlateGrey"},
        hoverinfo="none",
        mode="lines",
    )
    # Put it on the first layer of the figure.
    traces.append(edge_trace)

    # Nodes
    # Draws each node with the properties specified in `nodes_properties`.
    for node_properties in nodes_properties:
        node_x = []
        node_y = []
        node_descr = []
        for node in node_properties.positions:
            node_position = node_properties.positions[node]

            node_x.append(node_position["x"])
            node_y.append(node_position["y"])

            node_position = node_properties.positions[node]
            node_details = node_properties.mapping[str(node)]

            node_details = node_properties.mapping[str(node)]
            node_type = node_properties.node_type.title()
            node_label = "<br>".join(wrap(node_details.name, width=label_width))
            if isinstance(node_details, Operator):
                node_descr.append(
                    [
                        node_type,
                        node_label,
                        node_details.description,
                    ]
                )
            else:
                node_descr.append(
                    [
                        node_type,
                        node_label,
                        "",
                    ]
                )

        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            customdata=node_descr,
            text=[label[: label_width - 3] + "..." for _, label, _ in node_descr],
            textposition="bottom center",
            marker_symbol="square",
            marker={
                "size": markersize,
                "color": node_properties.color,
                "line": {"width": 2, "color": "DarkSlateGrey"},
            },
            hovertemplate="<b>%{customdata[1]}</b><br>Type: %{customdata[0]}<br>%{customdata[2]}<extra></extra>",
        )
        # Put the nodes on the next layer of the figure
        traces.append(node_trace)

    # Put figure together
    fig = go.Figure(
        data=traces,
        layout=go.Layout(
            title=dag.metadata.name,
            titlefont_size=16,
            margin={"b": 20, "l": 50, "r": 50, "t": 40},
            showlegend=False,
            hovermode="closest",
            xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
        ),
    )
    # Show figure
    fig.show()
