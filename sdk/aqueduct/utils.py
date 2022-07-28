import inspect
import json
import os
import shutil
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

import cloudpickle as cp
import pandas as pd
import requests
from aqueduct.enums import OperatorType
from aqueduct.operators import Operator
from croniter import croniter

from ._version import __version__
from .dag import DAG, RetentionPolicy, Schedule
from .enums import TriggerType
from .error import *
from .logger import Logger
from .templates import op_file_content

# Auth headers
API_KEY_HEADER = "api-key"

# Client version header
CLIENT_VERSION = "sdk-client-version"


def format_header_for_print(header: str) -> str:
    """Used to print the header of a section in "describe()" with a consistent length.

    Sandwiches the "header" argument with a repeating sequence of "="s. Eg.

    ============================ "predict" artifact ==========================
    [       prefix len          ]
    [                              full_len                                   ]
    """
    prefix_len = 20
    full_len = 80
    return f"{'=' * prefix_len} {header} {'=' * max(0, full_len - prefix_len - len(header))}"


def generate_auth_headers(api_key: str) -> Dict[str, str]:
    return {API_KEY_HEADER: api_key, CLIENT_VERSION: str(__version__)}


def generate_uuid() -> uuid.UUID:
    return uuid.uuid4()


WORKFLOW_UI_ROUTE_TEMPLATE = "/workflow/%s"
WORKFLOW_RUN_UI_ROUTE_TEMPLATE = "?workflowDagResultId=%s"


def generate_ui_url(
    aqueduct_base_address: str, workflow_id: str, result_id: Optional[str] = None
) -> str:
    if result_id:
        url = "%s%s%s" % (
            aqueduct_base_address,
            WORKFLOW_UI_ROUTE_TEMPLATE % workflow_id,
            WORKFLOW_RUN_UI_ROUTE_TEMPLATE % result_id,
        )
    else:
        url = "%s%s" % (
            aqueduct_base_address,
            WORKFLOW_UI_ROUTE_TEMPLATE % workflow_id,
        )
    return url


def raise_errors(response: requests.Response) -> None:
    def _extract_err_msg() -> str:
        resp_json = response.json()
        if "error" not in resp_json:
            raise Exception("No 'error' field on response: %s" % json.dumps(resp_json))
        return str(resp_json["error"])

    if response.status_code == 400:
        raise InvalidRequestError(_extract_err_msg())
    if response.status_code == 403:
        raise ClientValidationError(_extract_err_msg())
    elif response.status_code == 422:
        raise UnprocessableEntityError(_extract_err_msg())
    elif response.status_code == 500:
        raise InternalServerError(_extract_err_msg())
    elif response.status_code == 404:
        raise ResourceNotFoundError(_extract_err_msg())
    elif response.status_code != 200:
        raise AqueductError(_extract_err_msg())


def schedule_from_cron_string(schedule_str: str) -> Schedule:
    if len(schedule_str) == 0:
        return Schedule(trigger=TriggerType.MANUAL)

    if not croniter.is_valid(schedule_str):
        raise InvalidCronStringException("%s is not a valid cron string!" % schedule_str)

    return Schedule(trigger=TriggerType.PERIODIC, cron_schedule=schedule_str)


def retention_policy_from_latest_runs(k_latest_runs: int) -> RetentionPolicy:
    return RetentionPolicy(k_latest_runs=k_latest_runs)


# Helpers for creating model zip file

MODEL_FILE_NAME = "model.py"
MODEL_PICKLE_FILE_NAME = "model.pkl"
AQUEDUCT_UTILS_FILE_NAME = "aqueduct_utils.py"
PYTHON_VERSION_FILE_NAME = "python_version.txt"
CONDA_VERSION_FILE_NAME = "conda_version.txt"
RESERVED_FILE_NAMES = [
    MODEL_FILE_NAME,
    MODEL_PICKLE_FILE_NAME,
    AQUEDUCT_UTILS_FILE_NAME,
    PYTHON_VERSION_FILE_NAME,
    CONDA_VERSION_FILE_NAME,
]
REQUIREMENTS_FILE = "requirements.txt"
BLACKLISTED_REQUIREMENTS = "aqueduct"

UserFunction = Callable[..., Any]
MetricFunction = Callable[..., float]
CheckFunction = Callable[..., bool]


def get_zip_file_path(dir_name: str) -> str:
    return dir_name + ".zip"


def delete_zip_folder_and_file(dir_name: str) -> None:
    zip_file_path = get_zip_file_path(dir_name)

    if os.path.isfile(zip_file_path):
        os.remove(zip_file_path)

    if os.path.exists(dir_name):
        shutil.rmtree(dir_name)


def make_zip_dir() -> str:
    """
    Given a base path, creates an unique directory and returns the path.
    """
    created = False
    # Try to create the directory. If it already exists, try again with a new name.
    while not created:
        dir_path = Path(tempfile.gettempdir()) / str(uuid.uuid4())
        try:
            os.mkdir(dir_path)
            created = True
        except FileExistsError:
            pass
    return str(dir_path)


def serialize_function(
    func: Union[UserFunction, MetricFunction, CheckFunction],
    file_dependencies: Optional[List[str]] = None,
    reqs_path: Optional[str] = None,
) -> bytes:
    """
    Takes a user-defined function and packages it into a zip file structure expected by the backend.

    Arguments:
        func:
            The function to package
        file_dependencies:
            List of file dependencies the function uses
        reqs_path:
            A path to file that specify requirements

    Returns:
        filepath of zip file in string format
    """
    dir_path = None
    try:
        dir_path = make_zip_dir()
        zip_file_path = get_zip_file_path(dir_path)

        _package_files_and_requirements(
            func, os.path.join(os.getcwd(), dir_path), file_dependencies, reqs_path
        )

        with open(os.path.join(dir_path, MODEL_FILE_NAME), "w") as model_file:
            model_file.write(op_file_content())
        with open(os.path.join(dir_path, MODEL_PICKLE_FILE_NAME), "wb") as f:
            cp.dump(func, f)

        _make_archive(dir_path, zip_file_path)

        return open(zip_file_path, "rb").read()

    finally:
        if dir_path:
            delete_zip_folder_and_file(dir_path)


def _package_files_and_requirements(
    func: Union[UserFunction, MetricFunction, CheckFunction],
    dir_path: str,
    file_dependencies: Optional[List[str]] = None,
    reqs_path: Optional[str] = None,
) -> None:
    """
    Creates the temporary directory for the function with all file dependencies and
    requirements.txt.

    Arguments:
        func:
            User-defined function to package
        dir_path:
            Absolute path of directory to create.
        file_dependencies:
            Paths of file dependencies the function uses. Note that the paths are relative to the
            file the function is defined in.
        reqs_path:
            A path of file that specifies the requirements of the operator.
            Default path: /requirements.txt in the folder where the function is located

    """
    if not file_dependencies:
        file_dependencies = []

    current_directory_path = os.getcwd()

    func_filepath = inspect.getsourcefile(func)
    if not func_filepath:
        raise Exception("Unable to find source file of function.")
    # In Python3.8, `inspect.getsourcefile` only returns the file's relative path,
    # so we need the line below to get the absolute path.
    func_filepath = os.path.abspath(func_filepath)
    func_dirpath = os.path.dirname(func_filepath)

    # We check if the directory `func_dirpath` exists. If not, this means `func` is from within a
    # Jupyter notebook that the user is currently running, so we don't switch the working directory.
    # The goal of switching the working directory is that if a user specifies relative paths
    # in `file_dependencies` and if `func` is imported from a Python script located in another
    # directory, we can locate them.
    if os.path.isdir(func_dirpath):
        os.chdir(func_dirpath)

    for file_index, file_path in enumerate(file_dependencies):
        if file_path in RESERVED_FILE_NAMES:
            # If the user uploads a `model.py` file as a dependency, we will error out.
            raise ReservedFileNameException(
                "%s is a reserved file name in our system. Please rename your file. " % file_path
            )
        if not os.path.exists(file_path):
            raise InvalidFunctionException("File %s does not exist" % file_path)

        if not os.path.abspath(file_path).startswith(os.getcwd()):
            raise InvalidDependencyFilePath(
                "File %s cannot be outside of the directory containing the function" % file_path
            )

        dstfolder = os.path.dirname(os.path.join(dir_path, file_path))
        if not os.path.exists(dstfolder):
            os.makedirs(dstfolder)
        shutil.copy(file_path, os.path.join(dir_path, file_path))
    if reqs_path:
        if os.path.exists(reqs_path):
            Logger.logger.info("Installing requirements found at {path}".format(path=reqs_path))
            shutil.copy(reqs_path, os.path.join(dir_path, REQUIREMENTS_FILE))
        else:
            raise FileNotFoundError("Requirement file provided does not exist.")
    elif os.path.exists(REQUIREMENTS_FILE):
        Logger.logger.info(
            "%s: requirements.txt file detected in current directory %s, will not self-generate by inferring package dependencies."
            % (os.getcwd(), func.__name__)
        )
        shutil.copy(REQUIREMENTS_FILE, os.path.join(dir_path, REQUIREMENTS_FILE))
    else:
        Logger.logger.info(
            "%s: No requirements.txt file detected, self-generating file by inferring package dependencies."
            % func.__name__
        )
    # Figure out the python version
    python_version = ".".join((str(x) for x in sys.version_info[:2]))
    with open(os.path.join(dir_path, PYTHON_VERSION_FILE_NAME), "w") as f:
        f.write(python_version)

    os.chdir(current_directory_path)


def _make_archive(source: str, destination: str) -> None:
    """Creates zip file from source directory to destination file."""
    base = os.path.basename(destination)
    split_base = base.split(".")
    name = Path(".".join(split_base[:-1])).name
    format = split_base[-1]
    archive_from = os.path.dirname(source)
    if not archive_from:
        archive_from = "."
    archive_to = os.path.basename(source.strip(os.sep))
    shutil.make_archive(name, format, archive_from, archive_to)
    shutil.move("%s.%s" % (name, format), destination)


def artifact_name_from_op_name(op_name: str) -> str:
    return op_name + " artifact"


def generate_extract_op_name(
    dag: DAG,
    integration_name: str,
    name: Optional[str],
) -> str:
    """
    Generates name for extract operators to avoid operators with the same name.

    Arguments:
        dag:
            DAG that operator will be a part of.
        integration_name:
            Name of integration to run extract on.
        name:
            Optinally provided operator name.
    Returns:
        Name for extract operator.
    """

    op_name = name

    default_op_prefix = "%s query" % integration_name
    default_op_index = 1
    while op_name is None:
        candidate_op_name = default_op_prefix + " %d" % default_op_index
        colliding_op = dag.get_operator(with_name=candidate_op_name)
        if colliding_op is None:
            op_name = candidate_op_name  # break out of the loop!
        default_op_index += 1

    assert op_name is not None

    return op_name


def get_checks_for_op(op: Operator, dag: DAG) -> List[Operator]:
    check_operators = []
    for artf in op.outputs:
        check_operators.extend(
            dag.list_operators(
                filter_to=[OperatorType.CHECK],
                on_artifact_id=artf,
            )
        )
    return check_operators


def get_metrics_for_op(op: Operator, dag: DAG) -> List[Operator]:
    metric_operators = []
    for artf in op.outputs:
        metric_operators.extend(
            dag.list_operators(
                filter_to=[OperatorType.METRIC],
                on_artifact_id=artf,
            )
        )
    return metric_operators


def get_description_for_check(check: Operator) -> Dict[str, str]:
    check_spec = check.spec.check
    if check_spec:
        level = check_spec.level
    else:
        raise AqueductError("Check artifact malformed.")
    return {
        "Label": check.name,
        "Description": check.description,
        "Level": level,
    }


def get_description_for_metric(
    metric: Operator, dag: DAG
) -> Dict[str, Union[str, List[Mapping[str, Any]]]]:
    metric_spec = metric.spec.metric
    if metric_spec:
        granularity = metric_spec.function.granularity
    else:
        raise AqueductError("Metric artifact malformed.")
    return {
        "Label": metric.name,
        "Description": metric.description,
        "Granularity": granularity,
        "Checks": [
            get_description_for_check(check_op) for check_op in get_checks_for_op(metric, dag)
        ],
        "Metrics": [
            get_description_for_metric(metric_op, dag)
            for metric_op in get_metrics_for_op(metric, dag)
        ],
    }


def human_readable_timestamp(ts: int) -> str:
    format = "%Y-%m-%d %H:%M:%S"
    return datetime.utcfromtimestamp(ts).strftime(format)


def parse_user_supplied_id(id: Union[str, uuid.UUID]) -> str:
    """Verifies that a user-defined id is of the expected types, returning the string version of the id."""
    if not isinstance(id, str) and not isinstance(id, uuid.UUID):
        raise InvalidUserArgumentException("Provided id must be either str or uuid.")

    if isinstance(id, uuid.UUID):
        return str(id)
    return id
