import json
from typing import List

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

from aqueduct_executor.operators.connectors.tabular import config, connector, extract, load, common


class BigQueryConnector(connector.TabularConnector):
    def __init__(self, config: config.BigQueryConfig):
        self.project_id = config.project_id

        credentials_info = json.loads(config.service_account_credentials)
        self.credentials = service_account.Credentials.from_service_account_info(credentials_info)
        self.client = bigquery.Client(credentials=self.credentials, project=self.project_id)

    def authenticate(self) -> None:
        # There is no explicit authenticate method, so we execute a test query
        self.client.query("SELECT 1;")

    def discover(self) -> List[str]:
        all_tables = []
        for dataset in self.client.list_datasets():
            tables = self.client.list_tables(dataset.dataset_id)
            all_tables.extend([table.full_table_id.split(":")[-1] for table in tables])
        return all_tables

    def extract(self, params: extract.RelationalParams) -> pd.DataFrame:
        assert params.usable(), "Query is not usable. Did you forget to expand placeholders?"
        query = self.client.query(params.query)
        df = query.result().to_dataframe()
        return df

    def load(self, params: load.RelationalParams, df: pd.DataFrame) -> None:
        update_mode = params.update_mode
        write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE  # Default
        if update_mode == common.UpdateMode.APPEND:
            write_disposition = bigquery.WriteDisposition.WRITE_APPEND
        if update_mode == common.UpdateMode.REPLACE:
            write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE
        if update_mode == common.UpdateMode.FAIL:
            write_disposition = bigquery.WriteDisposition.WRITE_EMPTY
        # Since string columns use the "object" dtype, pass in a (partial) schema
        # to ensure the correct BigQuery data type.
        partial_schema = []
        for column in df:
            if df[column].dtype == object:
                partial_schema.append(bigquery.SchemaField(column, "STRING"))

        job_config = bigquery.LoadJobConfig(
            schema=partial_schema, write_disposition=write_disposition
        )
        job = self.client.load_table_from_dataframe(df, params.table, job_config=job_config)

        # Wait for the load job to complete.
        job.result()
