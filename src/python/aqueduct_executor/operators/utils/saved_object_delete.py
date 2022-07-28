from pydantic import BaseModel


class SavedObjectDelete(BaseModel):
    """This contains the result of deleting the saved object."""

    name: str
    succeeded: bool
