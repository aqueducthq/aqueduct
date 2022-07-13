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
        dag_file = compile(spec)
        data = str.encode(dag_file)
        utils.write_compile_airflow_output(storage, spec.output_content_path, data)
        utils.write_operator_metadata(storage, spec.metadata_path, err="", logs={})
    except Exception as e:
        traceback.print_exc()
        utils.write_operator_metadata(storage, spec.metadata_path, err=str(e), logs={})
        sys.exit(1)

def compile(spec: spec.CompileAirflowSpec) -> str:
    """
    Takes a CompileAirflowSpec and generates an Airflow DAG specification Python file.
    It returns the DAG file.
    """

    # Init Airflow tasks
    tasks = []
    task_to_alias = {}
    i = 0
    for task_id, task_spec in spec.task_specs.items():

        # Todo figure out dependencies

        alias = "t{}".format(i)
        t = Task(task_id, task_spec, alias)
        tasks.append(t)
        i += 1

        task_to_alias[task_id] = alias

    home = os.environ.get("HOME")
    path = os.path.join(home, ".aqueduct", "server/bin")
    env = Environment(loader=FileSystemLoader(path))

    print('The current working directory is: ', os.getcwd())
    print('The path is ', path)

    template = env.get_template("dag.template")
    r = template.render(
        dag_id=spec.dag_id,
        tasks=tasks,
        edges=spec.task_edges,
        task_to_alias=task_to_alias,
    )

    return r
    