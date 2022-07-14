import argparse
import base64
import json

from aqueduct_executor.operators.connectors.tabular import (
    execute,
    spec,
)

from pydantic import parse_obj_as


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--spec", required=True)
    args = parser.parse_args()

    spec_json = base64.b64decode(args.spec)
    data = json.loads(spec_json)
    # TODO (ENG-1286): https://linear.app/aqueducthq/issue/ENG-1286/investigate-why-mypy-is-complaining-about-object-parsing
    # The following line is working, but mypy complains:
    # Argument 1 to "parse_obj_as" has incompatible type "object"; expected "Type[<nothing>]"
    # We ignore the error for now.
    spec = parse_obj_as(spec.Spec, spec_json) # type: ignore

    execute.run(spec)