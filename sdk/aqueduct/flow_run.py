import textwrap
import uuid
from textwrap import wrap
from typing import Any, Dict, List, Mapping, Optional, Union

import plotly.graph_objects as go
from aqueduct.artifact import Artifact, get_artifact_type
from aqueduct.check_artifact import CheckArtifact
from aqueduct.dag import DAG
from aqueduct.enums import ArtifactType, DisplayNodeType, ExecutionStatus, OperatorType
from aqueduct.error import InternalAqueductError
from aqueduct.metric_artifact import MetricArtifact
from aqueduct.operators import Operator
from aqueduct.param_artifact import ParamArtifact
from aqueduct.table_artifact import TableArtifact
from aqueduct.utils import format_header_for_print, generate_ui_url, human_readable_timestamp

from aqueduct import api_client


class FlowRun:
    """This class is a read-only handle corresponding to a single workflow run in the system."""

    def __init__(
        self,
        flow_id: str,
        run_id: str,
        in_notebook_or_console_context: bool,
        dag: DAG,
        created_at: int,
        status: ExecutionStatus,
    ):
        assert run_id is not None
        self._flow_id = flow_id
        self._id = run_id
        self._in_notebook_or_console_context = in_notebook_or_console_context
        self._dag = dag
        self._created_at = created_at
        self._status = status

    def id(self) -> uuid.UUID:
        """Returns the id for this flow run."""
        return uuid.UUID(self._id)

    def status(self) -> ExecutionStatus:
        """Returns the status of the flow run."""
        return self._status

    def describe(self) -> None:
        """Prints out a human-readable description of the flow run."""

        url = generate_ui_url(
            api_client.__GLOBAL_API_CLIENT__.construct_base_url(),
            self._flow_id,
            self._id,
        )

        print(
            textwrap.dedent(
                f"""
            {format_header_for_print(f"'{self._dag.metadata.name}' Run")}
            ID: {self._id}
            Created At (UTC): {human_readable_timestamp(self._created_at)}
            Status: {str(self._status)}
            UI: {url}
            """
            )
        )

        param_artifacts = self._dag.list_artifacts(filter_to=[ArtifactType.PARAM])
        print(format_header_for_print("Parameters "))
        for param_artifact in param_artifacts:
            param_op = self._dag.must_get_operator(with_output_artifact_id=param_artifact.id)
            assert param_op.spec.param is not None, "Artifact is not a parameter."
            print("* " + param_op.name + ": " + param_op.spec.param.val)

    def artifact(
        self, name: str
    ) -> Optional[Union[TableArtifact, MetricArtifact, CheckArtifact, ParamArtifact]]:
        """Gets the Artifact from the flow run based on the name of the artifact.

        Args:
            name:
                the name of the artifact.

        Returns:
            A input artifact obtained from the dag attached to the flow run.
            If the artifact does not exist, return None.
        """
        flow_run_dag = self._dag
        artifact_from_dag = flow_run_dag.get_artifacts_by_name(name)

        if artifact_from_dag is None:
            return None
        elif get_artifact_type(artifact_from_dag) is ArtifactType.TABLE:
            return TableArtifact(self._dag, artifact_from_dag.id, from_flow_run=True)
        elif get_artifact_type(artifact_from_dag) is ArtifactType.NUMBER:
            return MetricArtifact(self._dag, artifact_from_dag.id, from_flow_run=True)
        elif get_artifact_type(artifact_from_dag) is ArtifactType.BOOL:
            return CheckArtifact(self._dag, artifact_from_dag.id, from_flow_run=True)
        elif get_artifact_type(artifact_from_dag) is ArtifactType.PARAM:
            return ParamArtifact(self._dag, artifact_from_dag.id, from_flow_run=True)

        raise InternalAqueductError("The artifact's type can not be recognized.")


# TODO(ENG-1049): find a better place to put this. It cannot be put in utils.py because of
#  a circular dependency with `api_client.py`. We should move `api_client.py` to an
#  internal directory.
def _show_dag(
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
    operator_positions, artifact_positions = api_client.__GLOBAL_API_CLIENT__.get_node_positions(
        operator_mapping
    )

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
