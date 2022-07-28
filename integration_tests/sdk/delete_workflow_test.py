from time import sleep

import pytest
from aqueduct.error import InvalidRequestError
from constants import SENTIMENT_SQL_QUERY
from utils import (
    delete_flow,
    generate_new_flow_name,
    get_integration_name,
    run_flow_test,
)

from aqueduct import LoadUpdateMode

LIST_INTEGRATION_OBJECTS_TEMPLATE = "/api/integration/%s/objects"


@pytest.mark.publish
def test_delete_workflow_invalid_saved_objects(client):
    integration = client.integration(name=get_integration_name())
    name = generate_new_flow_name()
    flow_id = None

    ###

    table = integration.sql(query=SENTIMENT_SQL_QUERY)

    table.save(integration.config(table="delete_table", update_mode=LoadUpdateMode.REPLACE))

    flow_id = run_flow_test(client, [table], name=name, num_runs=1, delete_flow_after=False).id()

    ###

    try:
        tables = client.flow(flow_id).list_saved_objects()
        tables[get_integration_name()][0].object_name = "I_DON_T_EXIST"
        tables[get_integration_name()] = [tables[get_integration_name()][0]]

        with pytest.raises(InvalidRequestError):
            data = client.delete_flow(flow_id, saved_objects_to_delete=tables, force=True)
    finally:
        delete_flow(client, flow_id)
