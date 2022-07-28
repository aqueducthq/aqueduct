from typing import Any, List

from aqueduct.aqueduct_client import Client, get_apikey
from aqueduct.constants import exports
from aqueduct.decorator import check, metric, op, to_operator
from aqueduct.enums import CheckSeverity, LoadUpdateMode
from aqueduct.flow import Flow
from aqueduct.schedule import DayOfMonth, DayOfWeek, Hour, Minute, daily, hourly, monthly, weekly


# Retrieves all valid import paths for all variables in a given module, using the import path prefix
# When you add a constant module, call this function to generate a
# `aqueduct.SUPPORTED_<MODULE_NAME>` field to let user know valid import paths
# for your module.
#
# For example, if the module `exports` contains two constants, `CSV` and `JSON`,
# __getAllImportPathsForModule(exports, 'aqueduct.exports') generates an array
# ['aqueduct.exports.CSV', 'aqueduct.exports.JSON']
# which are import paths users can copy-paste.
def __getAllImportPathsForModule(module: Any, prefix: str) -> List[str]:
    return [
        f"{prefix}.{varName}"
        for varName, val in module.__dict__.items()
        if not callable(val)  # Ignore functions
        and not varName.startswith("__")  # Ignore internal attributes
        and getattr(val, "__module__", None) is None  # Ignore recursive imports
    ]


# Allows users to access aqueduct.METADATA_FIELDS to see all valid imports from the metadata module.
SUPPORTED_EXPORTS = __getAllImportPathsForModule(exports, "aqueduct.exports")
