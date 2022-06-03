from aqueduct_executor.operators.connectors.tabular import config, relational
from sqlalchemy import create_engine, engine


class SqliteConnector(relational.RelationalConnector):
    def __init__(self, config: config.SqliteConfig):
        conn_engine = _create_engine(config)
        super().__init__(conn_engine)


def _create_engine(config: config.SqliteConfig) -> engine.Engine:
    # SQLite Dialect:
    # https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#dialect-sqlite-pysqlite-connect
    url = "sqlite:///{database}".format(
        database=config.database,
    )
    return create_engine(url)
