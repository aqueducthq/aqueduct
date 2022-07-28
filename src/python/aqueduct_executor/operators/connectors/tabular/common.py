from enum import Enum

from aqueduct_executor.operators.utils import enums


class Name(Enum, metaclass=enums.MetaEnum):
    POSTGRES = "Postgres"
    SNOWFLAKE = "Snowflake"
    BIG_QUERY = "BigQuery"
    REDSHIFT = "Redshift"
    SQL_SERVER = "SQL Server"
    MYSQL = "MySQL"
    MARIA_DB = "MariaDB"
    AZURE_SQL = "AzureSQL"
    S3 = "S3"
    SQLITE = "SQLite"
    AQUEDUCT_DEMO = "Aqueduct Demo"


class UpdateMode(Enum, metaclass=enums.MetaEnum):
    APPEND = "append"
    REPLACE = "replace"
    FAIL = "fail"


class S3TabularFormat(Enum, metaclass=enums.MetaEnum):
    JSON = "JSON"
    CSV = "CSV"
    PARQUET = "Parquet"
