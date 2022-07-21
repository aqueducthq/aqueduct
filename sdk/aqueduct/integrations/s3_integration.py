import json
from typing import List, Optional, Union

from aqueduct.api_client import APIClient
from aqueduct.artifact import Artifact, ArtifactSpec
from aqueduct.dag import DAG, AddOrReplaceOperatorDelta, apply_deltas_to_dag
from aqueduct.enums import S3FileFormat
from aqueduct.integrations.integration import Integration, IntegrationInfo
from aqueduct.operators import (
    ExtractSpec,
    Operator,
    OperatorSpec,
    S3ExtractParams,
    S3LoadParams,
    SaveConfig,
)
from aqueduct.table_artifact import DataArtifact
from aqueduct.utils import artifact_name_from_op_name, generate_extract_op_name, generate_uuid


class S3Integration(Integration):
    """
    Class for S3 integration.
    """

    def __init__(self, api_client: APIClient, dag: DAG, metadata: IntegrationInfo):
        self._api_client = api_client
        self._dag = dag
        self._metadata = metadata

    def file(
        self,
        filepaths: Union[List[str], str],
        format: S3FileFormat,
        name: Optional[str] = None,
        description: str = "",
        data_type: Optional[str] = None,
    ) -> DataArtifact:
        """
        Retrieves a file from the S3 integration.

        Args:
            filepaths:
                Filepath to retrieve from. The filepaths can either be:
                1) a single string that represents a file name or a directory name. The directory
                name must ends with a `/`. In case of a file name, we attempt to retrieve that file,
                and in case of a directory name, we do a prefix search on the directory and retrieve
                all matched files and concatenate them into a single file.
                2) a list of strings representing the file name. Note that in this case, we do not
                accept directory names in the list.
            name:
                Name of the query.
            description:
                Description of the query.

        Returns:
            DataArtifact representing the S3 File.
        """
        integration_info = self._metadata

        op_name = generate_extract_op_name(self._dag, integration_info.name, name)

        operator_id = generate_uuid()
        output_artifact_id = generate_uuid()
        apply_deltas_to_dag(
            self._dag,
            deltas=[
                AddOrReplaceOperatorDelta(
                    op=Operator(
                        id=operator_id,
                        name=op_name,
                        description=description,
                        spec=OperatorSpec(
                            extract=ExtractSpec(
                                service=integration_info.service,
                                integration_id=integration_info.id,
                                parameters=S3ExtractParams(
                                    filepath=json.dumps(filepaths), 
                                    format=format,
                                    data_type=data_type
                                ),
                            )
                        ),
                        outputs=[output_artifact_id],
                    ),
                    output_artifacts=[
                        Artifact(
                            id=output_artifact_id,
                            name=artifact_name_from_op_name(op_name),
                            spec=ArtifactSpec(table={}),
                        ),
                    ],
                )
            ],
        )

        return DataArtifact(
            api_client=self._api_client,
            dag=self._dag,
            artifact_id=output_artifact_id,
        )

    def config(self, filepath: str, format: S3FileFormat) -> SaveConfig:
        """
        Configuration for saving to S3 Integration.

        Arguments:
            filepath:
                S3 Filepath to save to.
            format:
                S3 Fileformat to save as. Can be CSV, JSON, or Parquet.
        Returns:
            SaveConfig object to use in DataArtifact.save()
        """
        return SaveConfig(
            integration_info=self._metadata,
            parameters=S3LoadParams(filepath=filepath, format=format),
        )

    def describe(self) -> None:
        """Prints out a human-readable description of the S3 integration."""
        print("==================== S3 Integration  =============================")
        self._metadata.describe()
