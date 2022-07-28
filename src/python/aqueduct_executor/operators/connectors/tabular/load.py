from typing import Union

from aqueduct_executor.operators.connectors.tabular import common, models
from pydantic import validator


class RelationalParams(models.BaseParams):
    table: str
    update_mode: common.UpdateMode = common.UpdateMode.REPLACE

    class Config:
        validate_assignment = True

    @validator("update_mode")
    def set_update_mode(cls, update_mode):  # type: ignore
        if update_mode == "":
            return common.UpdateMode.REPLACE
        return update_mode


class S3Params(models.BaseParams):
    filepath: str
    format: common.S3TabularFormat


Params = Union[RelationalParams, S3Params]
