import pandas as pd
import pytest
from aqueduct_executor.operators.connectors.tabular import connector


def authenticate_test(conn: connector.StorageConnector):
    try:
        conn.authenticate()
    except ConnectionError as e:
        pytest.fail("Failed authentication %s" % e)


def load_test(conn: connector.StorageConnector, params: dict, df: pd.DataFrame):
    conn.load(params, df)


def extract_test(conn: connector.StorageConnector, params: dict, expected_df: pd.DataFrame):
    df = conn.extract(params)
    dup = pd.concat([df, expected_df]).drop_duplicates(keep=False)
    if dup.shape[0] != 0:
        pytest.fail(
            "Extracted dataframe does not match expected dataframe.\n Actual DF:\n {}\n Expected DF:\n {}\n".format(
                df, expected_df
            )
        )


def sample_df() -> pd.DataFrame:
    return pd.read_csv("https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv")
