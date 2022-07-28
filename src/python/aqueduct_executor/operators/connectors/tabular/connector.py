from abc import ABC, abstractmethod
from typing import Any, List

import pandas as pd
from aqueduct_executor.operators.connectors.tabular import extract, load
from aqueduct_executor.operators.utils.enums import ArtifactType


class StorageConnector(ABC):
    @abstractmethod
    def authenticate(self) -> None:
        """Authenticates connector configuration. Raises a ConnectionError if there is an error."""

    @abstractmethod
    def discover(self) -> List[str]:
        """Discover items in the connection.

        Returns:
            A list of items discovered.
        """

    @abstractmethod
    def extract(  # type: ignore
        self,
        # TODO (ENG-1285): Revisit the typing issue that araises from inheritence
        params,  # extract.Params
    ) -> Any:
        """Extracts data from source into a DataFrame.

        Args:
            params: Extract parameters for the connector.

        Returns:
            A DataFrame that contains the data extracted by the connector.
        """

    @abstractmethod
    def load(  # type: ignore
        self,
        # TODO (ENG-1285): Revisit the typing issue that araises from inheritence
        params,  # load.Params
        data: Any,
        artifact_type: ArtifactType,
    ) -> None:
        """Loads data into destination storage integration.

        Args:
            params: Load parameters for the connector.
            data: data to load.
            artifact_type: type of the artifact.
        """
