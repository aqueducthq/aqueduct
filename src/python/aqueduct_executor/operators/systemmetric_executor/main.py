import argparse
import base64
import traceback
import sys

from aqueduct_executor.operators.utils import enums, utils
from aqueduct_executor.operators.systemmetric_executor import spec
from aqueduct_executor.operators.utils.storage.parse import parse_storage


def run(spec: spec.SystemMetricSpec) -> None:
    """
    Executes a system metric operator by storing the requested system metrics value in the output content path.
    """
    storage = parse_storage(spec.storage_config)
    system_metadata = utils.read_system_metadata(storage, spec.input_metadata_paths)
    print("=====")
    print(spec.metricname)
    print("=====")
    #runtime = system_metadata[0]["logs"]["runtime"]
    utils.write_artifact(
            storage,
            spec.output_content_paths[0],
            spec.output_metadata_paths[0],
            float(system_metadata[0]["SystemMetadata"]["time"]),
            {},
            enums.OutputArtifactType.FLOAT,
        )
    utils.write_operator_metadata(storage, spec.metadata_path, "", {})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--spec", required=True)
    args = parser.parse_args()

    spec_json = base64.b64decode(args.spec)
    spec = spec.parse_spec(spec_json)

    print("Job Spec: \n{}".format(spec.json()))
    run(spec)
