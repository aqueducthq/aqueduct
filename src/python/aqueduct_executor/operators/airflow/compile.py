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
    1. Using the workflow_name, we generate a dag_id. This is just going to be
    workflow_name.
    2. For each operator found in `specs`, we iterate over the operator and generate a Task
    instance for it. This will be used to generate the task_id, which is simply the operator
    name, an alias (we do this once the edges have been created).
    3. Determine the python requirements for each of the tasks. For function operators, this
    is going to require reading the function file and taking a look at the requirements.txt
    file. For extract and load operators, we simply lookup the hardcoded mapping for the
    system requirements. For example, Postgres operations would need to install psycopg2, 
    while Snowflake operations would need to install snowflakedb.
    4. Generate the template and get the response as bytes.
    5. Write the bytes to the storage location found at output_content_path.
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
