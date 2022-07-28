import io
import json
from typing import Any, List
from PIL import Image
import cloudpickle as pickle
import numpy as np

import boto3
import pandas as pd
from aqueduct_executor.operators.connectors.tabular import common, config, connector, extract, load
from aqueduct_executor.operators.utils.enums import ArtifactType

_DEFAULT_JSON_ENCODING = "utf8"
_DEFAULT_IMAGE_FORMAT = "jpeg"


class S3Connector(connector.StorageConnector):
    def __init__(self, config: config.S3Config):
        self.s3 = boto3.resource(
            "s3",
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
        )

        self.bucket = config.bucket

    def authenticate(self) -> None:
        bucket = self.s3.Bucket(self.bucket)
        # Below is a low-overhead way of checking if the user has access to the bucket.
        # Source: https://stackoverflow.com/a/49817544
        if not bucket.creation_date:
            raise Exception(
                "Bucket does not exist or you do not have permission to access the bucket."
            )

    def discover(self) -> List[str]:
        raise Exception("Discover is not supported for S3.")

    def _fetch_object(self, key: str, params: extract.S3Params) -> Any:
        response = self.s3.Object(self.bucket, key).get()
        data = response["Body"].read()
        if params.artifact_type == ArtifactType.TABULAR:
            if params.format is None:
                raise Exception("You must specify a file format for tabular data.")
            buf = io.BytesIO(data)
            if params.format == common.S3TabularFormat.CSV:
                return pd.read_csv(buf)
            elif params.format == common.S3TabularFormat.JSON:
                return pd.read_json(buf)
            elif params.format == common.S3TabularFormat.PARQUET:
                return pd.read_parquet(buf)
            raise Exception("Unknown S3 file format %s." % params.format)
        elif params.artifact_type == ArtifactType.JSON:
            # This assumes that the encoding is "utf-8". May worth considering letting the user
            # specify custom encoding in the future.
            json_data = data.decode(_DEFAULT_JSON_ENCODING)
            # Make sure the data is a valid json object.
            json.loads(json_data)
            return json_data
        elif params.artifact_type == ArtifactType.IMAGE:
            return Image.open(io.BytesIO(data))
        elif params.artifact_type == ArtifactType.BYTES:
            return data
        elif (params.artifact_type == ArtifactType.STRING or
              params.artifact_type == ArtifactType.BOOL or
              params.artifact_type == ArtifactType.NUMERIC or
              params.artifact_type == ArtifactType.DICT or
              params.artifact_type == ArtifactType.TUPLE or
              params.artifact_type == ArtifactType.PICKLABLE):
            unpickled_data = pickle.loads(data)

            if params.artifact_type == ArtifactType.STRING:
                assert(isinstance(unpickled_data, str))
            elif params.artifact_type == ArtifactType.BOOL:
                assert(isinstance(unpickled_data, bool) or isinstance(unpickled_data, np.bool_))
            elif params.artifact_type == ArtifactType.NUMERIC:
                assert(isinstance(unpickled_data, int) or isinstance(unpickled_data, float) or isinstance(unpickled_data, np.number))
            elif params.artifact_type == ArtifactType.DICT:
                assert(isinstance(unpickled_data, dict))
            elif params.artifact_type == ArtifactType.TUPLE:
                assert(isinstance(unpickled_data, tuple))
            
            return unpickled_data
        else:
            raise Exception("Unsupported data type %s." % params.artifact_type)

    def extract(self, params: extract.S3Params) -> Any:
        path = json.loads(params.filepath)
        if not isinstance(path, List):
            if len(path) == 0:
                raise Exception("S3 file path cannot be an empty string.")
            if path[-1] == "/":
                # This means the path is a directory, and we will do a prefix search.
                files = []
                for obj in self.s3.Bucket(self.bucket).objects.filter(Prefix=path):
                    # The filter api also returns the directories, so we filter them out.
                    if (obj.key)[-1] != "/":
                        files.append(self._fetch_object(obj.key, params))

                if params.artifact_type == ArtifactType.TABULAR and params.merge:
                    return pd.concat(files)
                else:
                    return tuple(files)
            else:
                # This means the path is a file name, and we do a regular file retrieval.
                return self._fetch_object(path, params)
        else:
            # This means we have a list of file paths.
            files = []
            for key in path:
                if len(key) == 0:
                    raise Exception("S3 file path cannot be an empty string.")
                if key[-1] == "/":
                    raise Exception("Each key in the list must not be a directory, found %s." % key)
                files.append(self._fetch_object(key, params))
            
            if params.artifact_type == ArtifactType.TABULAR and params.merge:
                return pd.concat(files)
            else:
                return tuple(files)

    def load(self, params: load.S3Params, data: Any, artifact_type: ArtifactType) -> None:
        if artifact_type == ArtifactType.TABULAR:
            if params.format is None:
                raise Exception("You must specify a file format for tabular data.")
            buf = io.BytesIO(data)
            if params.format == common.S3TabularFormat.CSV:
                data.to_csv(buf, index=False)
            elif params.format == common.S3TabularFormat.JSON:
                # Index cannot be False for `to.json` for default orient
                # See: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_json.html
                data.to_json(buf)
            elif params.format == common.S3TabularFormat.PARQUET:
                data.to_parquet(buf, index=False)
            else:
                raise Exception("Unknown S3 file format %s." % params.format)
            serialized_data = buf.getvalue()
        elif artifact_type == ArtifactType.JSON:
            serialized_data = data.encode(_DEFAULT_JSON_ENCODING)
        elif artifact_type == ArtifactType.IMAGE:
            img_bytes = io.BytesIO()
            data.save(img_bytes, format=_DEFAULT_IMAGE_FORMAT)
            serialized_data = img_bytes.getvalue()
        elif artifact_type == ArtifactType.BYTES:
            serialized_data = data
        elif (artifact_type == ArtifactType.STRING or
              artifact_type == ArtifactType.BOOL or
              artifact_type == ArtifactType.NUMERIC or
              artifact_type == ArtifactType.DICT or
              artifact_type == ArtifactType.TUPLE or
              artifact_type == ArtifactType.PICKLABLE):
            serialized_data = pickle.dumps(data)
        else:
            raise Exception("Unsupported data type %s." % artifact_type)

        self.s3.Object(self.bucket, params.filepath).put(Body=serialized_data)
