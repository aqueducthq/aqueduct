import os
import subprocess
import sys
from pathlib import Path

import pytest
import requests

import aqueduct


class TestBackend:
    GET_WORKFLOW_TABLES_TEMPLATE = "/api/workflow/%s/tables"
    WORKFLOW_PATH = Path(__file__).parent / "setup"

    @classmethod
    def setup_class(cls):
        cls.client = aqueduct.Client(pytest.api_key, pytest.server_address)
        cls.flows = {}

        workflow_files = [
            f
            for f in os.listdir(cls.WORKFLOW_PATH)
            if os.path.isfile(os.path.join(cls.WORKFLOW_PATH, f))
        ]
        for workflow in workflow_files:
            proc = subprocess.Popen(
                [
                    "python3",
                    os.path.join(cls.WORKFLOW_PATH, workflow),
                    pytest.api_key,
                    pytest.server_address,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            out, err = proc.communicate()
            out = out.decode("utf-8")
            err = err.decode("utf-8")
            if err:
                raise Exception(f"Could not run workflow {workflow}.\n\n{err}")
            else:
                cls.flows[workflow] = out.strip().split()[-1]

    @classmethod
    def teardown_class(cls):
        for flow in cls.flows:
            cls.client.delete_flow(cls.flows[flow])

    @classmethod
    def get_response_class(cls, endpoint, additional_headers={}):
        headers = {"api-key": pytest.api_key}
        headers.update(additional_headers)
        url = aqueduct.api_client.__GLOBAL_API_CLIENT__.construct_full_url(endpoint)
        r = requests.get(url, headers=headers)
        return r

    def test_endpoint_getworkflowtables(self):
        endpoint = self.GET_WORKFLOW_TABLES_TEMPLATE % self.flows["changing_saves.py"]
        data = self.get_response_class(endpoint).json()["table_details"]

        assert len(data) == 3

        # table_name, update_mode
        data_set = set(
            [
                ("table_1", "append"),
                ("table_1", "replace"),
                ("table_2", "append"),
            ]
        )
        assert set([(item["table_name"], item["update_mode"]) for item in data]) == data_set

        # Check all in same integration
        assert len(set([item["integration_id"] for item in data])) == 1
        assert len(set([item["service"] for item in data])) == 1
