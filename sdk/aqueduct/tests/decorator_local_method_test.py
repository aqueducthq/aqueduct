from aqueduct.decorator import op,metric,check
from aqueduct.tests.utils import (
    default_table_artifact,
)
inp = default_table_artifact()

@op
def op_fn_with_parentheses(df):
    pass
print(op_fn_with_parentheses.local.__name__)

@check()
def check_fn_with_parentheses(df):
    pass
print(check_fn_with_parentheses.local)

@metric()
def metric_fn_with_parentheses(df):
    pass
print(metric_fn_with_parentheses.local())