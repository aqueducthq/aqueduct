import pandas as pd
import io
from PIL import Image
from typing import Any
import json
import cloudpickle as pickle

_DEFAULT_ENCODING = "utf8"


def read_tabular_content(content: bytes) -> pd.DataFrame:
    return pd.read_json(io.BytesIO(content), orient="table")


def read_json_content(content: bytes) -> Any:
    return json.loads(content.decode(_DEFAULT_ENCODING))


def read_pickle_content(content: bytes) -> Any:
    return pickle.loads(content)


def read_image_content(content: bytes) -> Image.Image:
    return Image.open(io.BytesIO(content))


def read_standard_content(content: bytes) -> str:
    return content.decode(_DEFAULT_ENCODING)


def read_bytes_content(content: bytes) -> bytes:
    return content
