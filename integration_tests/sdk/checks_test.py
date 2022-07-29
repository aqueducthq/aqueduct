import pandas as pd
import pytest
from aqueduct.error import AqueductError, ArtifactNotFoundException, InvalidUserActionException
from constants import CHURN_SQL_QUERY, SENTIMENT_SQL_QUERY
from test_metrics.constant.model import constant_metric
from utils import get_integration_name, run_flow_test, run_sentiment_model

from aqueduct import CheckSeverity, check


@check()
def success_on_single_table_input(df):
    if not isinstance(df, pd.DataFrame):
        raise Exception("Expected dataframe as input to check, got %s" % type(df).__name__)
    return True


@check()
def success_on_single_metric_input(metric):
    if not isinstance(metric, float):
        raise Exception("Expected float as input to check, got %s" % type(metric).__name__)
    return True


@check()
def success_on_multiple_mixed_inputs(metric, df):
    if not isinstance(metric, float):
        raise Exception("Expected float as input to check, got %s" % type(metric).__name__)
    if not isinstance(df, pd.DataFrame):
        raise Exception("Expected dataframe as input to check, got %s" % type(df).__name__)
    return True


def test_check_on_table(client):
    """Test check on a function operator."""
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)
    check_artifact = success_on_single_table_input(sql_artifact)
    assert check_artifact.get()

    run_flow_test(client, artifacts=[check_artifact])


def test_check_on_metric(client):
    """Test check on a metric operator."""
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)
    metric = constant_metric(sql_artifact)

    check_artifact = success_on_single_metric_input(metric)
    assert check_artifact.get()

    run_flow_test(client, artifacts=[check_artifact])


def test_check_on_multiple_mixed_inputs(client):
    """Test check on multiple tables and metrics."""
    db = client.integration(name=get_integration_name())
    sql_artifact1 = db.sql(query=SENTIMENT_SQL_QUERY)
    metric = constant_metric(sql_artifact1)

    sql_artifact2 = db.sql(query=SENTIMENT_SQL_QUERY)
    table = run_sentiment_model(sql_artifact2)

    check_artifact = success_on_multiple_mixed_inputs(metric, table)
    assert check_artifact.get()

    run_flow_test(client, artifacts=[check_artifact])


def test_edit_check(client):
    """Test that checks can be edited by replacing with the same name."""
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)

    @check()
    def check_op(df):
        return False

    failed_check = check_op(sql_artifact)
    assert not failed_check.get()

    @check()
    def check_op(df):
        return True

    success_check = check_op(sql_artifact)
    assert success_check.get()

    # Attempting to fetch the previous check artifact should fail, since its been overwritten!
    with pytest.raises(ArtifactNotFoundException):
        failed_check.get()


def test_delete_check(client):
    """Test that checks can be deleted by name."""
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)

    with pytest.raises(InvalidUserActionException):
        sql_artifact.remove_check(name="nonexistant_check")

    check_artifact_on_sql = success_on_single_table_input(sql_artifact)
    sql_artifact.remove_check(name="success_on_single_table_input")
    with pytest.raises(ArtifactNotFoundException):
        check_artifact_on_sql.get()

    metric_artifact = constant_metric(sql_artifact)
    check_artifact_on_metric = success_on_single_table_input(metric_artifact)
    metric_artifact.remove_check(name="success_on_single_table_input")
    with pytest.raises(ArtifactNotFoundException):
        check_artifact_on_metric.get()


def test_check_wrong_input_type(client):
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)

    # User function receives a dataframe when it's expecting a metric.
    check_artifact = success_on_single_metric_input(sql_artifact)
    with pytest.raises(AqueductError):
        check_artifact.get()

    # TODO(ENG-862): the following code this should not surface an internal error,
    #  since its the user's fault.
    # Running a function operator on a check output, which is not allowed.
    check_artifact = success_on_single_table_input(sql_artifact)
    fn_artifact = run_sentiment_model(check_artifact)
    with pytest.raises(Exception):
        fn_artifact.get()


def test_check_wrong_number_of_inputs(client):
    db = client.integration(name=get_integration_name())
    sql_artifact1 = db.sql(query=SENTIMENT_SQL_QUERY)
    sql_artifact2 = db.sql(query=SENTIMENT_SQL_QUERY)
    check_artifact = success_on_single_table_input(sql_artifact1, sql_artifact2)

    # TODO(ENG-863): Do we want a more specific error here?
    with pytest.raises(AqueductError):
        check_artifact.get()


def test_check_with_numpy_bool_output(client):
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=CHURN_SQL_QUERY)

    @check()
    def success_check_return_numpy_bool(df):
        return df["total_charges"].mean() < 2500

    check_artifact = success_check_return_numpy_bool(sql_artifact)
    assert check_artifact.get()


def test_check_with_series_output(client):
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)

    @check()
    def success_check_return_series_of_booleans(df):
        return pd.Series([True, True, True])

    @check()
    def failure_check_return_series_of_booleans(df):
        return pd.Series([True, False, True])

    passed = success_check_return_series_of_booleans(sql_artifact)
    assert passed.get()

    failed = failure_check_return_series_of_booleans(sql_artifact)
    assert not failed.get()

    run_flow_test(client, artifacts=[sql_artifact, passed, failed])


@pytest.mark.publish
def test_check_failure_with_varying_severity(client):
    db = client.integration(name=get_integration_name())
    sql_artifact = db.sql(query=SENTIMENT_SQL_QUERY)

    # An error check will fail the workflow, but a warning check will not.
    @check(severity=CheckSeverity.WARNING)
    def failure_nonblocking_check(df):
        return False

    @check(severity=CheckSeverity.ERROR)
    def failure_blocking_check(df):
        return False

    nonblocking_check = failure_nonblocking_check(sql_artifact)
    run_flow_test(client, artifacts=[sql_artifact, nonblocking_check])

    blocking_check = failure_blocking_check(sql_artifact)
    run_flow_test(client, artifacts=[sql_artifact, blocking_check], expect_success=False)
