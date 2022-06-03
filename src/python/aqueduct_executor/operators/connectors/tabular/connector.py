from abc import ABC, abstractmethod
from typing import List

import pandas as pd
from aqueduct_executor.operators.connectors.tabular import extract, load


class TabularConnector(ABC):
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
    def extract(self, params: extract.Params) -> pd.DataFrame:
        """Extracts data from source into a DataFrame.

        Args:
            params: Extract parameters for the connector.

        Returns:
            A DataFrame that contains the data extracted by the connector.
        """

    @abstractmethod
    def load(self, params: load.Params, df: pd.DataFrame) -> None:
        """Loads DataFrame into destination.

        Args:
            params: Load parameters for the connector.
            df: DataFrame to load.
        """
