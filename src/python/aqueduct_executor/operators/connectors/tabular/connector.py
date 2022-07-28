from abc import ABC, abstractmethod
from typing import List

import pandas as pd
from aqueduct_executor.operators.connectors.tabular import extract, load
from aqueduct_executor.operators.utils.saved_object_delete import SavedObjectDelete


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
    def extract(  # type: ignore
        self,
        # TODO (ENG-1285): Revisit the typing issue that araises from inheritence
        params,  # extract.Params
    ) -> pd.DataFrame:
        """Extracts data from source into a DataFrame.

        Args:
            params: Extract parameters for the connector.

        Returns:
            A DataFrame that contains the data extracted by the connector.
        """

    @abstractmethod
    def delete(  # type: ignore
        self,
        # TODO (ENG-1285): Revisit the typing issue that araises from inheritence
        objects,  # List[str]
    ) -> List[SavedObjectDelete]:
        """Delete objects from integration.

        Args:
            objects: List of objects to delete from this integration.
        """

    @abstractmethod
    def load(  # type: ignore
        self,
        # TODO (ENG-1285): Revisit the typing issue that araises from inheritence
        params,  # load.Params
        df: pd.DataFrame,
    ) -> None:
        """Loads DataFrame into destination.

        Args:
            params: Load parameters for the connector.
            df: DataFrame to load.
        """
