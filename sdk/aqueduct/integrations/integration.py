import json
import uuid
from abc import ABC
from typing import Any

from aqueduct.enums import ServiceType
from pydantic import BaseModel


class IntegrationInfo(BaseModel):
    id: uuid.UUID
    name: str
    service: ServiceType
    createdAt: int
    validated: bool

    def describe(self) -> None:
        """Prints out a human-readable description of the integration."""
        description_map = {
            "Id": str(self.id),
            "Name": self.name,
            "Service": self.service,
            "CreatedAt": self.createdAt,
            "Validated": self.validated,
        }
        print(json.dumps(description_map, sort_keys=False, indent=4))


class Integration(ABC):
    """
    Abstract class for the various integrations Aqueduct interacts with.
    """

    _metadata: IntegrationInfo

    def __hash__(self) -> int:
        return hash(self._metadata.name)

    def __eq__(self, other: Any) -> bool:
        if type(other) == type(self) and "name" in other._metadata.__dict__:
            return bool(self._metadata.name == other._metadata.name)
        elif type(other) == str:
            return bool(self._metadata.name == other)
        return False
