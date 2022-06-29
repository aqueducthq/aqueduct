from typing import Dict, List, Any

import json
import pytest

from aqueduct.enums import ArtifactType
from aqueduct.error import InvalidUserArgumentException
from constants import SENTIMENT_SQL_QUERY
from utils import get_integration_name, run_flow_test, generate_new_flow_name, wait_for_flow_runs
from aqueduct import metric, op
import pandas as pd


@metric
def double_number_input(num: int) -> float:
    if not isinstance(num, int):
        raise Exception("Expected an integer input.")
    return float(2 * num)


@metric
def len_of_word(word: str) -> int:
    if not isinstance(word, str):
        raise Exception("Expected a string input.")
    return len(word)


@op
def convert_dict_to_df(kv: Dict[str, List[float]]):
    return pd.DataFrame(data=kv)


def test_basic_param_creation(client):
    # Parameter of integer type
    param = client.create_param(name="number", default=8)
    assert param.get() == 8

    param_doubled = double_number_input(param)
    assert param_doubled.get() == 2 * 8

    # Parameter of string type
    param = client.create_param(name="word", default="hello world")
    assert param.get() == "hello world"

    param_length = len_of_word(param)
    assert param_length.get() == len("hello world")

    # Parameter of dictionary type
    kv = {"col 1": [1.23, 4.56], "col 2": [7.89, 1.23]}
    param = client.create_param(name="word", default=kv)
    assert param.get() == kv

    kv_df = convert_dict_to_df(param)
    assert kv_df.get().equals(pd.DataFrame(data=kv))


def test_non_jsonable_parameter(client):
    with pytest.raises(InvalidUserArgumentException):
        _ = client.create_param(name="bad param", default=b"cant serialize me")

    param = client.create_param(name="number", default=8)
    param_doubled = double_number_input(param)
    with pytest.raises(InvalidUserArgumentException):
        _ = param_doubled.get(parameters={"number": b"cant serialize me"})


def test_get_with_custom_parameter(client):
    param = client.create_param(name="number", default=8)
    assert param.get() == 8

    param_doubled = double_number_input(param)
    assert param_doubled.get(parameters={"number": 20}) == 40
    assert param_doubled.get() == 2 * 8

    with pytest.raises(InvalidUserArgumentException):
        param_doubled.get(parameters={"non-existant param": 10})


@op
def append_row_to_df(df, row):
    """`row` is a list of values to append to the input dataframe."""
    df.loc[len(df.index)] = row
    return df


def test_parameter_in_basic_flow(client):
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)
    row_to_add = ["new hotel", "09-28-1996", "US", "It was new."]
    new_row_param = client.create_param(name="new row", default=row_to_add)
    output = append_row_to_df(sql_artifact, new_row_param)

    input_df = sql_artifact.get()
    input_df.loc[len(input_df.index)] = row_to_add

    output_df = output.get()
    assert output_df.equals(input_df)


def _check_param_vals(dag, expected_vals: List[Any]):
    """Check that all parameter artifacts have a one-to-one correspondence with `expected_vals`."""
    artifacts = dag.list_artifacts(filter_to=[ArtifactType.PARAM])
    for artifact in artifacts:
        op = dag.must_get_operator(with_output_artifact_id=artifact.id)
        param_val = json.loads(op.spec.param.val)
        assert param_val in expected_vals
        expected_vals.remove(param_val)


@pytest.mark.publish
def test_edit_param_for_flow(client):
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)
    row_to_add = ["new hotel", "09-28-1996", "US", "It was new."]
    new_row_param = client.create_param(name="new row", default=row_to_add)
    output = append_row_to_df(sql_artifact, new_row_param)

    flow_name = "Edit Parameter Test Flow"
    flow = run_flow_test(client, artifacts=[output], name=flow_name, delete_flow_after=False)
    flow_id = flow.id()

    try:
        # Edit the flow with a different row to append and re-publish
        new_row_to_add = ["another new hotel", "10-10-1000", "ID", "It was really really new."]
        new_row_param = client.create_param(name="new row", default=new_row_to_add)
        output = append_row_to_df(sql_artifact, new_row_param)

        # Wait for the first run, then refresh the workflow and verify that it runs at least
        # one more time (two runs total, since the original was manually triggered).
        flow = run_flow_test(
            client, artifacts=[output], name=flow_name, num_runs=2, delete_flow_after=False
        )

        # Verify that the parameters were edited as expected.
        flow_runs = flow.list_runs()
        assert len(flow_runs) == 2
        _check_param_vals(flow.fetch(flow_runs[1]["run_id"])._dag, [row_to_add])
        _check_param_vals(flow.latest()._dag, [new_row_to_add])

    finally:
        client.delete_flow(flow.id())

    assert flow_id == flow.id()


@metric
def add_numbers(sql, num1, num2):
    if not isinstance(num1, int) or not isinstance(num2, int):
        raise Exception("Expected an integer input.")
    return num1 + num2


@pytest.mark.publish
def test_trigger_flow_with_different_param(client):
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)

    num1 = client.create_param(name="num1", default=5)
    num2 = client.create_param(name="num2", default=5)
    output = add_numbers(sql_artifact, num1, num2)

    flow_name = generate_new_flow_name()
    flow = run_flow_test(client, artifacts=[output], name=flow_name, delete_flow_after=False)

    try:
        client.trigger(flow.id(), parameters={"num1": 10})
        assert wait_for_flow_runs(client, flow.id(), num_runs=2) == 2

        # Verify the parameters were configured as expected.
        flow_runs = flow.list_runs()
        assert len(flow_runs) == 2
        _check_param_vals(flow.fetch(flow_runs[1]["run_id"])._dag, [5, 5])
        _check_param_vals(flow.latest()._dag, [5, 10])
    finally:
        client.delete_flow(flow.id())


@pytest.mark.publish
def test_trigger_flow_with_different_sql_param(client):
    db = client.integration(name=get_integration_name())

    _ = client.create_param("table_name", default="hotel_reviews")
    sql_artifact = db.sql(query="select * from {{ table_name}}")

    flow_name = generate_new_flow_name()
    flow = run_flow_test(client, artifacts=[sql_artifact], name=flow_name, delete_flow_after=False)

    try:
        client.trigger(flow.id(), parameters={"table_name": "customer_activity"})
        assert wait_for_flow_runs(client, flow.id(), num_runs=2) == 2

        # Verify the parameters were configured as expected.
        flow_runs = flow.list_runs()
        assert len(flow_runs) == 2
        _check_param_vals(flow.fetch(flow_runs[1]["run_id"])._dag, expected_vals=["hotel_reviews"])
        _check_param_vals(flow.latest()._dag, expected_vals=["customer_activity"])
    finally:
        client.delete_flow(flow.id())
