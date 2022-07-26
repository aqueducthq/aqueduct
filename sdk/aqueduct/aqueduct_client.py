import json
import logging
import os
import uuid
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Union

import __main__ as main
import yaml
from aqueduct.generic_artifact import Artifact as GenericArtifact

from .api_client import APIClient
from .artifact import Artifact, ArtifactSpec
from .dag import (
    DAG,
    AddOrReplaceOperatorDelta,
    Metadata,
    SubgraphDAGDelta,
    apply_deltas_to_dag,
    validate_overwriting_parameters,
)
from .enums import RelationalDBServices, ServiceType
from .error import (
    IncompleteFlowException,
    InvalidIntegrationException,
    InvalidUserActionException,
    InvalidUserArgumentException,
)
from .flow import Flow
from .flow_run import _show_dag
from .github import Github
from .integrations.google_sheets_integration import GoogleSheetsIntegration
from .integrations.integration import Integration, IntegrationInfo
from .integrations.s3_integration import S3Integration
from .integrations.salesforce_integration import SalesforceIntegration
from .integrations.sql_integration import RelationalDBIntegration
from .operators import Operator, OperatorSpec, ParamSpec, serialize_parameter_value
from .param_artifact import ParamArtifact
from .responses import SavedObjectDelete, SavedObjectUpdate
from .utils import (
    generate_ui_url,
    generate_uuid,
    parse_user_supplied_id,
    retention_policy_from_latest_runs,
    schedule_from_cron_string,
)


def get_apikey() -> str:
    """
    Get the API key if the server is running locally.

    Returns:
        The API key.
    """
    server_directory = os.path.join(os.environ["HOME"], ".aqueduct", "server")
    config_file = os.path.join(server_directory, "config", "config.yml")
    with open(config_file, "r") as f:
        try:
            return str(yaml.safe_load(f)["apiKey"])
        except yaml.YAMLError as exc:
            print(
                "This API works only when you are running the server and the SDK on the same machine."
            )
            exit(1)


class Client:
    """This class allows users to interact with flows on their Aqueduct cluster."""

    def __init__(
        self,
        api_key: str,
        aqueduct_address: str,
        log_level: int = logging.ERROR,
    ):
        """Creates an instance of Client.

        Args:
            api_key:
                The user unique API key provided by Aqueduct.
            aqueduct_address:
                The address of the Aqueduct Server service.
            log_level:
                A indication of what level and above to print logs from the sdk.
                Defaults to printing error and above only. Types defined in: https://docs.python.org/3/howto/logging.html

        Returns:
            A Client instance.
        """
        logging.basicConfig(level=log_level)
        self._api_client = APIClient(api_key, aqueduct_address)
        self._connected_integrations: Dict[
            str, IntegrationInfo
        ] = self._api_client.list_integrations()
        self._dag = DAG(metadata=Metadata())

        # Will show graph if in an ipynb or Python console, but not if running a Python script.
        self._in_notebook_or_console_context = (not hasattr(main, "__file__")) and (
            not "PYTEST_CURRENT_TEST" in os.environ
        )

    def github(self, repo: str, branch: str = "") -> Github:
        """Retrieves a Github object connecting to specified repos and branch.

        You can only connect to a public repo if you didn't already connect a
        Github account to your Aqueduct account.

        Args:
            repo:
                The full github repo URL, e.g. "my_organization/my_repo"
            branch:
                Optional branch name. The default main branch will be used if not specified.

        Returns:
            A github integration object linked to the repo and branch.

        """
        return Github(client=self._api_client, repo_url=repo, branch=branch)

    def create_param(self, name: str, default: Any, description: str = "") -> ParamArtifact:
        """Creates a parameter artifact that can be fed into other operators.

        Parameter values are configurable at runtime.

        Args:
            name:
                The name to assign this parameter.
            default:
                The default value to give this parameter, if no value is provided.
                Every parameter must have a default.
            description:
                A description of what this parameter represents.

        Returns:
            A parameter artifact.
        """
        if default is None:
            raise InvalidUserArgumentException("Parameter default value cannot be None.")

        val = serialize_parameter_value(name, default)

        operator_id = generate_uuid()
        output_artifact_id = generate_uuid()
        apply_deltas_to_dag(
            self._dag,
            deltas=[
                AddOrReplaceOperatorDelta(
                    op=Operator(
                        id=operator_id,
                        name=name,
                        description=description,
                        spec=OperatorSpec(param=ParamSpec(val=val)),
                        inputs=[],
                        outputs=[output_artifact_id],
                    ),
                    output_artifacts=[
                        Artifact(
                            id=output_artifact_id,
                            name=name,
                            spec=ArtifactSpec(jsonable={}),
                        ),
                    ],
                )
            ],
        )
        return ParamArtifact(
            self._api_client,
            self._dag,
            output_artifact_id,
        )

    def list_integrations(self) -> Dict[str, IntegrationInfo]:
        """Retrieves a dictionary of integrations the client can use.

        Returns:
            A dictionary mapping from integration name to additional info.
        """
        self._connected_integrations = self._api_client.list_integrations()
        return self._connected_integrations

    def integration(
        self, name: str
    ) -> Union[
        SalesforceIntegration,
        S3Integration,
        GoogleSheetsIntegration,
        RelationalDBIntegration,
    ]:
        """Retrieves a connected integration object.

        Args:
            name:
                The name of the integration

        Returns:
            The integration object with the given name.

        Raises:
            InvalidIntegrationException:
                An error occurred because the cluster is not connected to the
                provided integration or the provided integration is of an
                incompatible type.
        """
        if name not in self._connected_integrations.keys():
            raise InvalidIntegrationException("Not connected to integration %s!" % name)

        integration_info = self._connected_integrations[name]
        if integration_info.service in RelationalDBServices:
            return RelationalDBIntegration(
                api_client=self._api_client,
                dag=self._dag,
                metadata=integration_info,
            )
        elif integration_info.service == ServiceType.SALESFORCE:
            return SalesforceIntegration(
                api_client=self._api_client,
                dag=self._dag,
                metadata=integration_info,
            )
        elif integration_info.service == ServiceType.GOOGLE_SHEETS:
            return GoogleSheetsIntegration(
                api_client=self._api_client,
                dag=self._dag,
                metadata=integration_info,
            )
        elif integration_info.service == ServiceType.S3:
            return S3Integration(
                api_client=self._api_client,
                dag=self._dag,
                metadata=integration_info,
            )
        else:
            raise InvalidIntegrationException(
                "This method does not support loading integration of type %s"
                % integration_info.service
            )

    def list_flows(self) -> List[Dict[str, str]]:
        """Lists the flows that are accessible by this client.

        Returns:
            A list of flows, each represented as a dictionary providing essential
            information (eg. name, id, etc.), which the user can use to inspect
            the flow further in the UI or SDK.
        """
        return [
            workflow_resp.to_readable_dict() for workflow_resp in self._api_client.list_workflows()
        ]

    def flow(self, flow_id: Union[str, uuid.UUID]) -> Flow:
        """Fetches a flow corresponding to the given flow id.

        Args:
             flow_id:
                Used to identify the flow to fetch from the system.

        Raises:
            InvalidUserArgumentException:
                If the provided flow id does not correspond to a flow the client knows about.
        """
        flow_id = parse_user_supplied_id(flow_id)

        if all(uuid.UUID(flow_id) != workflow.id for workflow in self._api_client.list_workflows()):
            raise InvalidUserArgumentException("Unable to find a flow with id %s" % flow_id)

        return Flow(
            self._api_client,
            flow_id,
            self._in_notebook_or_console_context,
        )

    def publish_flow(
        self,
        name: str,
        description: str = "",
        schedule: str = "",
        k_latest_runs: int = -1,
        artifacts: Optional[List[GenericArtifact]] = None,
    ) -> Flow:
        """Uploads and kicks off the given flow in the system.

        If a flow already exists with the same name, the existing flow will be updated
        to this new state.

        Args:
            name:
                The name of the newly created flow.
            description:
                A description for the new flow.
            schedule: A cron expression specifying the cadence that this flow
                will run on. If empty, the flow will only execute manually.
                For example, to run at the top of every hour:

                >> schedule = aqueduct.hourly(minute: 0)

            k_latest_runs:
                Number of most-recent runs of this flow that Aqueduct should store.
                Runs outside of this bound are deleted. Defaults to persisting all runs.
            artifacts:
                All the artifacts that you care about computing. These artifacts are guaranteed
                to be computed. Additional artifacts may also be included as intermediate
                computation steps. All checks are on the resulting flow are also included.
        Raises:
            InvalidCronStringException:
                An error occurred because the supplied schedule is invalid.
            IncompleteFlowException:
                An error occurred because you are missing some required fields or operators.

        Returns:
            A flow object handle to be used to fetch information about this productionized flow.
        """
        if artifacts is None or len(artifacts) == 0:
            raise IncompleteFlowException(
                "Must supply at least one output artifact when creating a flow."
            )

        cron_schedule = schedule_from_cron_string(schedule)
        retention_policy = retention_policy_from_latest_runs(k_latest_runs)

        dag = apply_deltas_to_dag(
            self._dag,
            deltas=[
                SubgraphDAGDelta(
                    artifact_ids=[artifact.id() for artifact in artifacts],
                    include_load_operators=True,
                    include_check_artifacts=True,
                ),
            ],
            make_copy=True,
        )
        dag.metadata = Metadata(
            name=name,
            description=description,
            schedule=cron_schedule,
            retention_policy=retention_policy,
        )

        flow_id = self._api_client.register_workflow(dag).id

        url = generate_ui_url(
            self._api_client.construct_base_url(),
            str(flow_id),
        )
        print("Url: ", url)

        return Flow(
            self._api_client,
            str(flow_id),
            self._in_notebook_or_console_context,
        )

    def trigger(
        self,
        flow_id: Union[str, uuid.UUID],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Immediately triggers another run of the provided flow.

        Args:
            flow_id:
                The id of the workflow to delete (not the name)
            parameters:
                A map containing custom values to use for the designated parameters. The mapping
                is expected to be from parameter name to the custom value. These custom values
                are not persisted to the workflow. To actually change the default parameter values
                edit the workflow itself through `client.publish_flow()`.

        Raises:
            InvalidRequestError:
                An error occurred when attempting to fetch the workflow to
                delete. The provided `flow_id` may be malformed.
            InternalServerError:
                An unexpected error occurred within the Aqueduct cluster.
        """
        if parameters is not None:
            flow = self.flow(flow_id)
            runs = flow.list_runs(limit=1)

            # NOTE: this is a defense check against triggering runs that haven't run yet.
            # We may want to revisit this in the future if more nuanced constraints are necessary.
            if len(runs) == 0:
                raise InvalidUserActionException(
                    "Cannot trigger a workflow that hasn't already run at least once."
                )
            validate_overwriting_parameters(flow.latest()._dag, parameters)

        serialized_params = None
        if parameters is not None:
            if any(not isinstance(name, str) for name in parameters):
                raise InvalidUserArgumentException("Parameters must be keyed by strings.")

            serialized_params = json.dumps(
                {name: serialize_parameter_value(name, val) for name, val in parameters.items()}
            )

        flow_id = parse_user_supplied_id(flow_id)
        self._api_client.refresh_workflow(flow_id, serialized_params)

    def delete_flow(
        self,
        flow_id: Union[str, uuid.UUID],
        saved_objects_to_delete: Optional[
            DefaultDict[Union[str, Integration], List[SavedObjectUpdate]]
        ] = None,
        force: bool = False,
    ) -> None:
        """Deletes a flow object.

        Args:
            flow_id:
                The id of the workflow to delete (not the name)
            saved_objects_to_delete:
                The tables or storage paths to delete grouped by integration name.
            force:
                Force the deletion even though some workflow-written objects in the writes_to_delete argument had UpdateMode=append

        Raises:
            InvalidRequestError:
                An error occurred when attempting to fetch the workflow to
                delete. The provided `flow_id` may be malformed.
            InternalServerError:
                An unexpected error occurred within the Aqueduct cluster.
        """
        if saved_objects_to_delete is None:
            saved_objects_to_delete = defaultdict()
        flow_id = parse_user_supplied_id(flow_id)

        # TODO(ENG-410): This method gives no indication as to whether the flow
        #  was successfully deleted.
        resp = self._api_client.delete_workflow(flow_id, saved_objects_to_delete, force)

        failed_deletions = {}
        counts = 0
        for integration in resp.saved_object_deletion_results:
            failed_for_integration = []
            for obj in resp.saved_object_deletion_results[integration]:
                if not obj.succeeded:
                    failed_for_integration.append(obj)
            if len(failed_for_integration) > 0:
                failed_deletions[str(integration)] = [
                    res.__dict__ for res in failed_for_integration
                ]
                counts += len(failed_for_integration)
        if counts > 0:
            failures = json.dumps(failed_deletions, sort_keys=False, indent=4)
            raise Exception(
                f"Workflow-Written Objects' Deletion Failures\n{counts} Failures\n{failures}"
            )

    def show_dag(self, artifacts: Optional[List[GenericArtifact]] = None) -> None:
        """Prints out the flow as a pyplot graph.

        A user outside the notebook environment will be redirected to a page in their browser
        containing the graph.

        Args:
            artifacts:
                If specified the subgraph terminating at these artifacts will be specified.
                Otherwise, the entire graph is printed.
        """
        dag = self._dag
        if artifacts is not None:
            dag = apply_deltas_to_dag(
                self._dag,
                deltas=[
                    SubgraphDAGDelta(
                        artifact_ids=[artifact.id() for artifact in artifacts],
                        include_load_operators=True,
                        include_check_artifacts=True,
                    ),
                ],
                make_copy=True,
            )
        _show_dag(self._api_client, dag)

    def describe(self) -> None:
        """Prints out info about this client in a human-readable format."""
        print("============================= Aqueduct Client =============================")
        print("Connected endpoint: %s" % self._api_client.aqueduct_address)
        print("Log Level: %s" % logging.getLevelName(logging.root.level))
        self._connected_integrations = self._api_client.list_integrations()
        print("Current Integrations:")
        for integrations in self._connected_integrations:
            print("\t -" + integrations)
