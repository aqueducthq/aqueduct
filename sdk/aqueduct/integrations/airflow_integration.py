from aqueduct.api_client import APIClient
from aqueduct.dag import DAG
from aqueduct.integrations.integration import IntegrationInfo, Integration


class AirflowIntegration(Integration):
    """
    Class for Airflow integration.
    """

    def __init__(self, api_client: APIClient, dag: DAG, metadata: IntegrationInfo):
        self._api_client = api_client
        self._dag = dag
        self._metadata = metadata


    def describe(self) -> None:
        """Prints out a human-readable description of the Airflow integration."""
        print("==================== Airflow Integration  =============================")
        self._metadata.describe()

