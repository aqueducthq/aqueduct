import pandas as pd
from aqueduct_executor.operators.connectors.tabular import config, load, relational
from sqlalchemy import create_engine, engine


class SqlServerConnector(relational.RelationalConnector):
    def __init__(self, config: config.SqlServerConfig):
        conn_engine = _create_engine(config)
        super().__init__(conn_engine)

    def load(self, params: load.RelationalParams, df: pd.DataFrame) -> None:
        # NOTE (saurav): PyODBC for SQL Server does not support `method="multi"` for `df.to_sql`,
        # which is why SqlServerConnector overrides `load`.
        df.to_sql(
            params.table,
            con=self.engine,
            if_exists="replace",
            index=False,
        )


def _create_engine(config: config.SqlServerConfig) -> engine.Engine:
    # SQL Server Dialect:
    # https://docs.sqlalchemy.org/en/14/dialects/mssql.html#dialect-mssql-pyodbc-connect
    url = "mssql+pyodbc://{username}:{password}@{host}:{port}/{database}?driver=ODBC+Driver+17+for+SQL+Server".format(
        username=config.username,
        password=config.password,
        host=config.host,
        port=config.port,
        database=config.database,
    )

    # We use `fast_executemany=True` to improve the performance of writing a large DataFrame.
    # https://docs.sqlalchemy.org/en/14/changelog/migration_13.html#support-for-pyodbc-fast-executemany
    return create_engine(url, fast_executemany=True)
