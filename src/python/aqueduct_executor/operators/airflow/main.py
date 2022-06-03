import argparse
import json
import base64

from aqueduct_executor.operators.airflow import spec, execute

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--spec", required=True)
    args = parser.parse_args()

    spec_json = base64.b64decode(args.spec)
    spec = spec.parse_spec(spec_json)

    execute.run(spec)
