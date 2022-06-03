from typing import Optional, Union

from aqueduct_executor.operators.connectors.tabular import models
from pydantic import Field


class BigQueryConfig(models.BaseConfig):
    project_id: str
    service_account_credentials: str


class MySqlConfig(models.BaseConfig):
    username: str
    password: str
    database: str
    host: str
    port: str


class PostgresConfig(models.BaseConfig):
    username: str
    password: str
    database: str
    host: str
    port: Optional[str] = "5432"


class S3Config(models.BaseConfig):
    access_key_id: str
    secret_access_key: str
    bucket: str


class SnowflakeConfig(models.BaseConfig):
    username: str
    password: str
    account_identifier: str
    database: str
    warehouse: str
    db_schema: Optional[str] = Field("public", alias="schema")  # schema is a Pydantic keyword


class SqlServerConfig(models.BaseConfig):
    username: str
    password: str
    database: str
    host: str
    port: str


class SqliteConfig(models.BaseConfig):
    database: str


Config = Union[
    BigQueryConfig,
    MySqlConfig,
    PostgresConfig,
    S3Config,
    SnowflakeConfig,
    SqlServerConfig,
    SqliteConfig,
]
