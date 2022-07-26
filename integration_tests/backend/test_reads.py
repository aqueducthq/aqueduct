import os
import subprocess
import sys
from pathlib import Path
from time import sleep

import pytest
import requests
import utils

import aqueduct


class TestReads:
    LIST_WORKFLOW_SAVED_OBJECTS_TEMPLATE = "/api/workflow/%s/objects"
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
                parsed = out.strip().split()
                cls.flows[workflow] = parsed[-2]
                n_runs = int(parsed[-1])
                utils.wait_for_flow_runs(cls.client, cls.flows[workflow], n_runs)

    @classmethod
    def teardown_class(cls):
        for flow in cls.flows:
            utils.delete_flow(cls.client, cls.flows[flow])

    @classmethod
    def get_response_class(cls, endpoint, additional_headers={}):
        headers = {"api-key": pytest.api_key}
        headers.update(additional_headers)
        url = cls.client._api_client.construct_full_url(endpoint)
        r = requests.get(url, headers=headers)
        return r

    def test_endpoint_list_saved_objects(self):
        endpoint = self.LIST_WORKFLOW_SAVED_OBJECTS_TEMPLATE % self.flows["changing_saves.py"]
        data = self.get_response_class(endpoint).json()["object_details"]

        assert len(data) == 3

        # table_name, update_mode
        data_set = set(
            [
                ("table_1", "append"),
                ("table_1", "replace"),
                ("table_2", "replace"),
            ]
        )
        assert set([(item["object_name"], item["update_mode"]) for item in data]) == data_set

        # Check all in same integration
        assert len(set([item["integration_name"] for item in data])) == 1
        assert len(set([item["service"] for item in data])) == 1
