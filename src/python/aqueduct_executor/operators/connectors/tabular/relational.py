from typing import Any, List

import pandas as pd
from aqueduct_executor.operators.connectors.tabular import connector, extract, load
from sqlalchemy import engine, inspect
from sqlalchemy.exc import SQLAlchemyError
from aqueduct_executor.operators.utils.enums import ArtifactType


class RelationalConnector(connector.StorageConnector):
    def __init__(self, conn_engine: engine.Engine):
        self.engine = conn_engine

    def __del__(self) -> None:
        self.engine.dispose()

    def authenticate(self) -> None:
        try:
            self.engine.connect()
        except SQLAlchemyError as e:
            raise ConnectionError("Unable to connect.") from e

    def discover(self) -> List[str]:
        return inspect(self.engine).get_table_names()  # type: ignore

    def extract(self, params: extract.RelationalParams) -> Any:
        assert params.usable(), "Query is not usable. Did you forget to expand placeholders?"
        return pd.read_sql(params.query, con=self.engine)

    def load(self, params: load.RelationalParams, df: Any, artifact_type: ArtifactType) -> None:
        if artifact_type != ArtifactType.TABULAR:
            raise Exception("The data being loaded must be of type tabular, found %s" % artifact_type)
        # NOTE (saurav): df._to_sql has known performance issues. Using `method="multi"` helps incrementally,
        # since pandas will pass multiple rows in a single INSERT. If this still remains an issue, we can pass in a
        # callable function for `method` that does bulk loading.
        # See: https://pandas.pydata.org/docs/user_guide/io.html#io-sql-method
        df.to_sql(
            params.table,
            con=self.engine,
            if_exists=params.update_mode.value,
            index=False,
            method="multi",
        )
