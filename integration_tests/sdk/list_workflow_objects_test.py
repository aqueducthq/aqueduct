import pytest
from constants import SENTIMENT_SQL_QUERY
from utils import delete_flow, generate_new_flow_name, get_integration_name, run_flow_test

from aqueduct import LoadUpdateMode


@pytest.mark.publish
def test_list_saved_objects(client):
    integration = client.integration(name=get_integration_name())
    name = generate_new_flow_name()
    flow_ids_to_delete = set()

    try:
        table = integration.sql(query=SENTIMENT_SQL_QUERY)

        table.save(integration.config(table="table_1", update_mode=LoadUpdateMode.REPLACE))

        # Tables don't already exist already so cannot append or replace it.
        flow_ids_to_delete.add(
            run_flow_test(client, [table], name=name, num_runs=1, delete_flow_after=False).id()
        )

        ###

        table = integration.sql(query=SENTIMENT_SQL_QUERY)

        table.save(integration.config(table="table_1", update_mode=LoadUpdateMode.APPEND))

        flow_ids_to_delete.add(
            run_flow_test(client, [table], name=name, num_runs=2, delete_flow_after=False).id()
        )

        ###

        table = integration.sql(query=SENTIMENT_SQL_QUERY)

        table.save(integration.config(table="table_1", update_mode=LoadUpdateMode.APPEND))

        flow_ids_to_delete.add(
            run_flow_test(client, [table], name=name, num_runs=3, delete_flow_after=False).id()
        )

        ###

        table = integration.sql(query=SENTIMENT_SQL_QUERY)

        table.save(integration.config(table="table_2", update_mode=LoadUpdateMode.REPLACE))

        flow_ids_to_delete.add(
            run_flow_test(client, [table], name=name, num_runs=4, delete_flow_after=False).id()
        )

        ###

        assert len(flow_ids_to_delete) == 1

        data = client.flow(list(flow_ids_to_delete)[0]).list_saved_objects()

        # Check all in same integration
        assert len(data.keys()) == 1

        # table_name, update_mode
        data_set = set(
            [
                ("table_1", LoadUpdateMode.APPEND),
                ("table_1", LoadUpdateMode.REPLACE),
                ("table_2", LoadUpdateMode.REPLACE),
            ]
        )
        integration_name = list(data.keys())[0]
        assert len(data[integration_name]) == 3
        assert (
            set([(item.object_name, item.update_mode) for item in data[integration_name]])
            == data_set
        )

        # Check mapping can be accessed correctly
        # Can be accessed by string of integration name
        assert len(data[get_integration_name()]) == 3
        # Can be accessed by Integration object with integration name
        assert len(data[integration]) == 3

    finally:
        for flow_id in flow_ids_to_delete:
            delete_flow(client, flow_id)
