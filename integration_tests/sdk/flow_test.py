from datetime import datetime, timedelta

import pytest
from aqueduct.error import IncompleteFlowException
from aqueduct.table_artifact import TableArtifact
from constants import SENTIMENT_SQL_QUERY
from test_functions.simple.model import dummy_model
from test_metrics.constant.model import constant_metric
from utils import (
    delete_flow,
    generate_new_flow_name,
    generate_table_name,
    get_integration_name,
    run_flow_test,
    run_sentiment_model,
    run_sentiment_model_multiple_input,
    wait_for_flow_runs,
)

import aqueduct
from aqueduct import LoadUpdateMode, check


def test_basic_flow(client):
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)
    output_artifact = run_sentiment_model(sql_artifact)
    output_artifact.save(
        config=db.config(table=generate_table_name(), update_mode=LoadUpdateMode.REPLACE)
    )

    run_flow_test(client, artifacts=[output_artifact])


def test_complex_flow(client):
    db = client.integration(name=get_integration_name())
    sql_artifact1 = db.sql(name="Query 1", query=SENTIMENT_SQL_QUERY)
    sql_artifact2 = db.sql(name="Query 2", query=SENTIMENT_SQL_QUERY)

    fn_artifact = run_sentiment_model_multiple_input(sql_artifact1, sql_artifact2)
    output_artifact = dummy_model(fn_artifact)
    output_artifact.save(
        config=db.config(table=generate_table_name(), update_mode=LoadUpdateMode.REPLACE)
    )

    @check()
    def successful_check(df):
        return True

    @check()
    def failing_check(df):
        return False

    run_flow_test(
        client,
        artifacts=[
            output_artifact,
            successful_check(output_artifact),
            failing_check(output_artifact),
        ],
    )


def test_multiple_output_artifacts(client):
    db = client.integration(name=get_integration_name())
    sql_artifact1 = db.sql(name="Query 1", query=SENTIMENT_SQL_QUERY)
    sql_artifact2 = db.sql(name="Query 2", query=SENTIMENT_SQL_QUERY)

    fn_artifact1 = run_sentiment_model(sql_artifact1)
    fn_artifact2 = dummy_model(sql_artifact2)
    fn_artifact1.save(
        config=db.config(table=generate_table_name(), update_mode=LoadUpdateMode.REPLACE)
    )
    fn_artifact2.save(
        config=db.config(table=generate_table_name(), update_mode=LoadUpdateMode.REPLACE)
    )

    run_flow_test(
        client,
        artifacts=[fn_artifact1, fn_artifact2],
    )


@pytest.mark.publish
def test_publish_with_schedule(client):
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)
    output_artifact = run_sentiment_model(sql_artifact)
    output_artifact.save(
        config=db.config(table=generate_table_name(), update_mode=LoadUpdateMode.REPLACE)
    )

    # Execute the flow 1 minute from now.
    execute_at = datetime.now() + timedelta(minutes=1)
    run_flow_test(
        client,
        artifacts=[output_artifact],
        schedule=aqueduct.hourly(minute=aqueduct.Minute(execute_at.minute)),
        num_runs=2,  # Wait for two runs because registering a workflow always triggers an immediate run first.
    )


def test_invalid_flow(client):
    with pytest.raises(IncompleteFlowException):
        client.publish_flow(
            name=generate_new_flow_name(),
            artifacts=[],
        )

    with pytest.raises(Exception):
        client.publish_flow(
            name=generate_new_flow_name(),
            artifacts=["123"],
        )


@pytest.mark.publish
def test_publish_flow_with_same_name(client):
    """Tests flow editing behavior."""
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)
    output_artifact = run_sentiment_model(sql_artifact)

    # Remember to cleanup any created test data.
    flow_ids_to_delete = set()
    try:
        flow_name = generate_new_flow_name()
        flow = run_flow_test(
            client,
            artifacts=[output_artifact],
            name=flow_name,
            schedule=aqueduct.daily(),
            delete_flow_after=False,
        )
        flow_ids_to_delete.add(flow.id())

        # Add a metric to the flow and re-publish under the same name.
        metric = constant_metric(output_artifact)
        flow = run_flow_test(
            client,
            artifacts=[metric],
            name=flow_name,
            schedule=aqueduct.daily(hour=aqueduct.Hour(1)),
            delete_flow_after=False,
        )
        flow_ids_to_delete.add(flow.id())
    finally:
        for flow_id in flow_ids_to_delete:
            delete_flow(client, flow_id)


@pytest.mark.publish
def test_refresh_flow(client):
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)
    output_artifact = run_sentiment_model(sql_artifact)
    output_artifact.save(
        config=db.config(table=generate_table_name(), update_mode=LoadUpdateMode.REPLACE)
    )
    flow = client.publish_flow(
        name=generate_new_flow_name(),
        artifacts=[output_artifact],
        schedule=aqueduct.hourly(),
    )

    # Wait for the first run, then refresh the workflow and verify that it runs at least
    # one more time.
    try:
        num_initial_runs = wait_for_flow_runs(client, flow.id())
        client.trigger(flow.id())
        wait_for_flow_runs(client, flow.id(), num_runs=num_initial_runs + 1)
    finally:
        client.delete_flow(flow.id())


@pytest.mark.publish
def test_get_artifact_from_flow(client):
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)
    output_artifact = run_sentiment_model(sql_artifact)
    output_artifact.save(
        config=db.config(table=generate_table_name(), update_mode=LoadUpdateMode.REPLACE)
    )
    flow = client.publish_flow(
        name=generate_new_flow_name(),
        artifacts=[output_artifact],
    )
    try:
        wait_for_flow_runs(client, flow.id(), num_runs=1)
        artifact_return = flow.latest().artifact(output_artifact.name())
        assert artifact_return.name() == output_artifact.name()
        assert artifact_return.get().equals(output_artifact.get())
    finally:
        client.delete_flow(flow.id())


@pytest.mark.publish
def test_get_artifact_reuse_for_computation(client):
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)
    output_artifact = run_sentiment_model(sql_artifact)
    output_artifact.save(
        config=db.config(table=generate_table_name(), update_mode=LoadUpdateMode.REPLACE)
    )
    flow = client.publish_flow(
        name=generate_new_flow_name(),
        artifacts=[output_artifact],
    )
    try:
        wait_for_flow_runs(client, flow.id(), num_runs=1)
        artifact_return = flow.latest().artifact(output_artifact.name())
        with pytest.raises(Exception):
            output_artifact = run_sentiment_model(artifact_return)
    finally:
        client.delete_flow(flow.id())
