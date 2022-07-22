from typing import List, Union

try:
    from typing import Literal
except ImportError:
    # Python 3.7 does not support typing.Literal
    from typing_extensions import Literal  # type: ignore

import json

from aqueduct_executor.operators.connectors.tabular import common, config, extract, load, models
from aqueduct_executor.operators.utils import enums
from aqueduct_executor.operators.utils.storage import config as sconfig
from pydantic import parse_obj_as, validator

AQUEDUCT_DEMO_NAME = "aqueduct_demo"


def unwrap_connector_config(cls, connector_config, values):  # type: ignore
    """
    TODO ENG-937: Remove this validator once connector config serialization is fixed.

    Unwraps the connector config before it can be parsed into a
    config.Config object. This is necessary because of how connector_config
    is serialized in Golang.

    For non-OAuth configs, it has the following structure:
    "connector_config": {
        "conf": {
            "username": "username",
            "password": "password",
        }
    }

    For OAuth configs, it has the following structure:
    "connector_config": {
        "token": {
            "access_token": "123456",
            "refresh_token": "123",
        },
        "oauth2_conf": {...},
        "public_conf": {...},
    }
    """

    if "connector_name" not in values:
        raise ValueError("Unknown connector name.")

    if not isinstance(connector_config, dict):
        raise ValueError("connector_config is not a dictionary.")

    if "conf" not in connector_config:
        # There is no inner `conf` dictionary to unwrap
        return connector_config

    if "conf" not in connector_config:
        # There is no inner `conf` dictionary to unwrap
        # This occurs when the spec is serialized in Python to run operators
        # on other engines.
        return connector_config

    # This is a static config
    return connector_config["conf"]


class AuthenticateSpec(models.BaseSpec):
    name: str
    type: Literal[enums.JobType.AUTHENTICATE]
    storage_config: sconfig.StorageConfig
    metadata_path: str
    connector_name: common.Name
    connector_config: config.Config

    # validators
    _unwrap_connector_config = validator("connector_config", allow_reuse=True, pre=True)(
        unwrap_connector_config
    )


class ExtractSpec(models.BaseSpec):
    name: str
    type: Literal[enums.JobType.EXTRACT]
    storage_config: sconfig.StorageConfig
    metadata_path: str
    connector_name: common.Name
    connector_config: config.Config
    parameters: extract.Params

    # The input fields are only used to record user-defined parameters for relational queries.
    # The tags in the queries will be expanded into the parameter values.
    input_param_names: List[str]
    input_content_paths: List[str]
    input_metadata_paths: List[str]  # This field is ignored and is only here for completeness.
    output_content_path: str
    output_metadata_path: str

    # validators
    _unwrap_connector_config = validator("connector_config", allow_reuse=True, pre=True)(
        unwrap_connector_config
    )


class LoadSpec(models.BaseSpec):
    name: str
    type: Literal[enums.JobType.LOAD]
    storage_config: sconfig.StorageConfig
    metadata_path: str
    connector_name: common.Name
    connector_config: config.Config
    parameters: load.Params
    input_content_path: str
    input_metadata_path: str

    # validators
    _unwrap_connector_config = validator("connector_config", allow_reuse=True, pre=True)(
        unwrap_connector_config
    )


class LoadTableSpec(models.BaseSpec):
    name: str
    type: Literal[enums.JobType.LOADTABLE]
    storage_config: sconfig.StorageConfig
    metadata_path: str
    connector_name: common.Name
    connector_config: config.Config
    csv: str
    load_parameters: LoadSpec

    # validators
    _unwrap_connector_config = validator("connector_config", allow_reuse=True, pre=True)(
        unwrap_connector_config
    )


class DiscoverSpec(models.BaseSpec):
    name: str
    type: Literal[enums.JobType.DISCOVER]
    storage_config: sconfig.StorageConfig
    metadata_path: str
    connector_name: common.Name
    connector_config: config.Config
    output_content_path: str

    # validators
    _unwrap_connector_config = validator("connector_config", allow_reuse=True, pre=True)(
        unwrap_connector_config
    )


Spec = Union[AuthenticateSpec, ExtractSpec, LoadSpec, LoadTableSpec, DiscoverSpec]


def parse_spec(spec_json: bytes) -> Spec:
    """
    Parses a JSON string into a Spec.
    """
    data = json.loads(spec_json)

    # TODO (ENG-1286): https://linear.app/aqueducthq/issue/ENG-1286/investigate-why-mypy-is-complaining-about-object-parsing
    # The following line is working, but mypy complains:
    # Argument 1 to "parse_obj_as" has incompatible type "object"; expected "Type[<nothing>]"
    # We ignore the error for now.
    return parse_obj_as(Spec, data)  # type: ignore
