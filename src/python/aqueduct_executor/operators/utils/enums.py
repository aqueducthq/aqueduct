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
    DISCOVER = "discover"
    PARAM = "param"
    SYSTEM_METRIC = "system_metric"


class ArtifactType(str, Enum, metaclass=MetaEnum):
    STRING = "string"
    BOOL = "boolean"
    NUMERIC = "numeric"
    DICT = "dictionary"
    TUPLE = "tuple"
    TABULAR = "tabular"
    JSON = "json"
    BYTES = "bytes"
    IMAGE = "image"
    PICKLABLE = "picklable"


class SerializationType(str, Enum, metaclass=MetaEnum):
    TABULAR = "tabular"
    JSON = "json"
    PICKLE = "pickle"
    IMAGE = "image"
    STANDARD = "standard"
    BYTES = "bytes"
