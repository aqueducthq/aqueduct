from enum import Enum, EnumMeta
from typing import Any, Iterable, cast


class MetaEnum(EnumMeta):
    """Allows to very easily check if strings are present in the enum, without a helper.
    Eg.
        if "Postgres" in ServiceType:
            ...
    """

    def __contains__(cls, item: Any) -> Any:
        return item in [v.value for v in cast(Iterable[Enum], cls.__members__.values())]


class ExecutionStatus(str, Enum, metaclass=MetaEnum):
    UNKNOWN = "unknown"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class FailureType(Enum, metaclass=MetaEnum):
    SYSTEM = 1
    USER = 2


class JobType(str, Enum, metaclass=MetaEnum):
    FUNCTION = "function"
    AUTHENTICATE = "authenticate"
    EXTRACT = "extract"
    LOAD = "load"
    LOADTABLE = "load-table"
    DELETESAVEDOBJECTS = "delete-saved-objects"
    DISCOVER = "discover"
    PARAM = "param"
    SYSTEM_METRIC = "system_metric"


class InputArtifactType(str, Enum, metaclass=MetaEnum):
    TABLE = "table"
    FLOAT = "float"
    JSON = "json"


class OutputArtifactType(str, Enum, metaclass=MetaEnum):
    TABLE = "table"
    FLOAT = "float"
    BOOL = "boolean"
    JSON = "json"
