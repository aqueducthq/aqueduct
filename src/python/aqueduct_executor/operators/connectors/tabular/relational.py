from typing import List

import pandas as pd
from sqlalchemy import engine, inspect
from sqlalchemy.exc import SQLAlchemyError

from aqueduct_executor.operators.connectors.tabular import connector, extract, load


class RelationalConnector(connector.TabularConnector):
    def __init__(self, conn_engine: engine.Engine):
        self.engine = conn_engine

    def __del__(self):
        self.engine.dispose()

    def authenticate(self) -> None:
        try:
            self.engine.connect()
        except SQLAlchemyError as e:
            raise ConnectionError("Unable to connect.") from e

    def discover(self) -> List[str]:
        return inspect(self.engine).get_table_names()

    def extract(self, params: extract.RelationalParams) -> pd.DataFrame:
        assert params.usable(), "Query is not usable. Did you forget to expand placeholders?"
        return pd.read_sql(params.query, con=self.engine)

    def load(self, params: load.RelationalParams, df: pd.DataFrame) -> None:
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
