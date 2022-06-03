import traceback
import sys

from aqueduct_executor.operators.airflow import spec
from aqueduct_executor.operators.utils import utils
from aqueduct_executor.operators.utils.storage import parse

from jinja2 import Environment, FileSystemLoader

def run(spec: spec.CompileAirflowSpec):
    """
    Executes a compile airflow operator.
    """
    print("Started %s job: %s" % (spec.type, spec.name))

    storage = parse.parse_storage(spec.storage_config)
    try:
        compile(spec)
        utils.write_operator_metadata(storage, spec.metadata_path, err="", logs={})
    except Exception as e:
        traceback.print_exc()
        utils.write_operator_metadata(storage, spec.metadata_path, err=str(e), logs={})
        sys.exit(1)

def compile(spec: spec.CompileAirflowSpec) -> bytes:
    """
    Takes a CompileAirflowSpec and generates an Airflow DAG specification Python file.
    It returns the DAG file.
    """

    # Init Airflow DAG id
    dag_id = "{}-{}".format(spec.workflow_id, spec.workflow_name)

    # Init Airflow tasks
    tasks = []
    for task_id, task_spec in spec.specs.items():
        # Todo figure out dependencies
        dependencies = []
        t = task.Task(task_id, task_spec, dependencies)
        tasks.append(t)

    env = Environment(loader=FileSystemLoader("./"))
    template = env.get_template("dag.template")
    r = template.render(
        dag_id="",
        tasks=tasks,
        edges=spec.edges,
    )
    return None
