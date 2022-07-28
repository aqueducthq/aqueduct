import uuid
from typing import Any, Dict, Optional

from aqueduct.enums import ArtifactType
from aqueduct.error import AqueductError
from pydantic import BaseModel


class ArtifactSpec(BaseModel):
    type: ArtifactType


class Artifact(BaseModel):
    id: uuid.UUID
    name: str
    spec: ArtifactSpec


def get_artifact_type(artifact: Artifact) -> ArtifactType:
    if artifact.spec.table is not None:
        return ArtifactType.TABLE
    if artifact.spec.float is not None:
        return ArtifactType.NUMBER
    if artifact.spec.bool is not None:
        return ArtifactType.BOOL
    if artifact.spec.jsonable is not None:
        return ArtifactType.PARAM
    else:
        raise AqueductError("Invalid operator type")
