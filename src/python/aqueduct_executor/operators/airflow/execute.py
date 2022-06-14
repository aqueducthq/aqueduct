from typing import Union
import traceback
import sys
import os

from aqueduct_executor.operators.airflow import spec
from aqueduct_executor.operators.connectors.tabular import spec as conn_spec
from aqueduct_executor.operators.function_executor import spec as func_spec
from aqueduct_executor.operators.param_executor import spec as param_spec
from aqueduct_executor.operators.utils import utils
from aqueduct_executor.operators.utils.storage import parse

from jinja2 import Environment, FileSystemLoader

TaskSpec = Union[conn_spec.ExtractSpec, conn_spec.LoadSpec, func_spec.FunctionSpec, param_spec.ParamSpec]

class Task:
    def __init__(self, task_id: str, spec: TaskSpec, alias: str):
        self.id = task_id
        self.spec = spec
        self.alias = alias

def run(spec: spec.CompileAirflowSpec):
    """
    Executes a compile airflow operator.
    """
    print("Started %s job: %s" % (spec.type, spec.name))

    storage = parse.parse_storage(spec.storage_config)
    try:
        compile(spec)
        # utils.write_operator_metadata(storage, spec.metadata_path, err="", logs={})
    except Exception as e:
        traceback.print_exc()
        # utils.write_operator_metadata(storage, spec.metadata_path, err=str(e), logs={})
        sys.exit(1)

def compile(spec: spec.CompileAirflowSpec) -> bytes:
    """
    Takes a CompileAirflowSpec and generates an Airflow DAG specification Python file.
    It returns the DAG file.
    """

    # Init Airflow tasks
    tasks = []
    i = 0
    for task_id, task_spec in spec.task_specs.items():
        
        # Todo figure out dependencies

        t = Task(task_id, task_spec, "t{}".format(i))
        tasks.append(t)
        i += 1

    env = Environment(loader=FileSystemLoader("./aqueduct_executor/operators/airflow"))

    print(os.getcwd())

    template = env.get_template("dag.template")
    r = template.render(
        dag_id=spec.dag_id,
        workflow_id=spec.workflow_id,
        tasks=tasks,
        edges=spec.edges,
    )

    with open('dag.py', "w") as f:
        f.write(r)

    return None
