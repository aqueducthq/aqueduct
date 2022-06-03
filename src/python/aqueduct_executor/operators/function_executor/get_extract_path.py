import argparse
import base64
import os

from aqueduct_executor.operators.function_executor.utils import OP_DIR

from . import spec

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--spec", required=True)
    args = parser.parse_args()

    spec_json = base64.b64decode(args.spec)
    spec = spec.parse_spec(spec_json)
    # The output of the print statement to stdout is captured by the calling bash script into a variable,
    # so we should not include any other print statements in this Python script.
    print(os.path.join(spec.function_extract_path, OP_DIR))
