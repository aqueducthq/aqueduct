from typing import Dict, List

import pandas as pd
from aqueduct_executor.operators.connectors.tabular import connector, extract, load
from aqueduct_executor.operators.utils.saved_object_delete import SavedObjectDelete
from sqlalchemy import MetaData, engine, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base


class RelationalConnector(connector.TabularConnector):
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

    def extract(self, params: extract.RelationalParams) -> pd.DataFrame:
        assert params.usable(), "Query is not usable. Did you forget to expand placeholders?"
        return pd.read_sql(params.query, con=self.engine)

    def delete(self, tables: List[str]) -> List[SavedObjectDelete]:
        results = []
        Base = declarative_base()
        metadata = MetaData()
        metadata.reflect(bind=self.engine)
        for table in tables:
            try:
                sql_table = metadata.tables[table]
                Base.metadata.drop_all(self.engine, [sql_table], checkfirst=True)
                results.append(SavedObjectDelete(name=table, succeeded=True))
            except:
                results.append(SavedObjectDelete(name=table, succeeded=False))
        return results

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
