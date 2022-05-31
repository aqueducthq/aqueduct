import argparse
import json
import base64
import traceback
import sys

from aqueduct_executor.operators.airflow import spec
from aqueduct_executor.operators.utils import utils
from aqueduct_executor.operators.utils.storage import parse

from pydantic import parse_obj_as
from jinja2 import Environment, FileSystemLoader

def run(spec: spec.CompileAirflowSpec):
    storage = parse.parse_storage(spec.storage_config)
    try:
        compile(spec)
        utils.write_operator_metadata(storage, spec.metadata_path, err="", logs={})
    except Exception as e:
        traceback.print_exc()
        utils.write_operator_metadata(storage, spec.metadata_path, err=str(e), logs={})
        sys.exit(1)

def compile(spec: spec.CompileAirflowSpec):
    '''
    - Collect list of operators and the input artifact ids and output artifacts. Using this list
    create a set of tasks that can be passed into the templating script.
    - Collect general DAG information from the workflow, such as Dag id and dag name?
    - Determine the python executable for each of the tasks. For each of these tasks we also need to
    know any special python virtual env libraries that need to be installed. This can be hardcoded for the
    extract and load operators (and params). For function this needs to be read from storage, as there is a
    requirements.txt file.
    '''
    env = Environment(loader=FileSystemLoader("./"))
    template = env.get_template("dag.template")
    r = template.render(
        dag_id="",
        tasks=None,
        edges=None,
    )
    return

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--spec", required=True)
    args = parser.parse_args()

    spec_json = base64.b64decode(args.spec)
    data = json.loads(spec_json)

    print("Job Spec: \n{}".format(json.dumps(data, indent=4)))

    job_spec = parse_obj_as(spec.CompileAirflowSpec)
    run(job_spec)
