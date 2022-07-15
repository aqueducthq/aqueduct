import argparse
import base64
import io
import os
import shutil
import sys
import traceback
import zipfile

from aqueduct_executor.operators.function_executor.spec import FunctionSpec, parse_spec
from aqueduct_executor.operators.function_executor.utils import OP_DIR
from aqueduct_executor.operators.utils.storage.parse import parse_storage
from aqueduct_executor.operators.utils.storage.storage import Storage


def _unzip_function_contents(function_in_bytes: bytes, extract_path: str) -> None:
    """
    Unzips raw function bytes into the current directory, assuming the bytes represent
    a zip file.
    """
    with zipfile.ZipFile(io.BytesIO(function_in_bytes), "r") as z:
        toplevel_dir = _extract_folder_name(z)
        for name in z.namelist():
            z.extract(name, extract_path)

        # Assumes all extracted file will be located in nested path.
        nested_path = os.path.join(extract_path, toplevel_dir)
        op_path = os.path.join(extract_path, OP_DIR)
        shutil.rmtree(op_path, ignore_errors=True)
        shutil.copytree(nested_path, op_path)
        shutil.rmtree(nested_path)


def _extract_folder_name(zip_ref: zipfile.ZipFile) -> str:
    """
    Given a zip file, return the name of the top-level folder.

    Assumption: The first item in namelist() is typically the name of the folder in
    which the files are extracted into. This is the same assumption `generate_foldername.sh`
    operates on.
    """
    folders = [folder for folder in zip_ref.namelist() if folder.endswith("/")]

    if len(folders) == 0:
        raise Exception("No folders found in zip file.")
    return folders[0]


def extract_function(storage: Storage, spec: FunctionSpec) -> None:
    """
    Extracts the user-specified function.
    """
    fn_path = spec.function_extract_path
    if not os.path.exists(fn_path):
        os.mkdir(fn_path)

    function_byte = storage.get(spec.function_path)
    _unzip_function_contents(
        function_in_bytes=function_byte,
        extract_path=fn_path,
    )


def run(spec: FunctionSpec) -> None:
    print("Job Spec: \n{}".format(spec.json()))

    try:
        storage = parse_storage(spec.storage_config)
        extract_function(storage, spec)
    except Exception as e:  # Catch all error types
        print("Exception Raised: ", e)
        traceback.print_tb(e.__traceback__)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--spec", required=True)
    args = parser.parse_args()

    spec_json = base64.b64decode(args.spec)
    spec = parse_spec(spec_json)

    run(spec)
