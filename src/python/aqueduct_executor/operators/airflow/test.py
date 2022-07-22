from aqueduct_executor.operators.airflow import execute, spec
from aqueduct_executor.operators.connectors.tabular import common, extract
from aqueduct_executor.operators.connectors.tabular import spec as conn_spec
from aqueduct_executor.operators.function_executor import spec as func_spec
from aqueduct_executor.operators.param_executor import spec as param_spec
from aqueduct_executor.operators.utils import enums
from aqueduct_executor.operators.utils.storage import config


def main() -> None:
    aspec = spec.CompileAirflowSpec(
        name="test_airflow",
        type=enums.JobType.COMPILE_AIRFLOW,
        storage_config=config.StorageConfig(
            type=config.StorageType.File,
            file_config=config.FileStorageConfig(
                directory="/Users/saurav/.aqueduct/server/storage"
            ),
        ),
        metadata_path="meta_path",
        output_content_path="airflow_dag.py",
        workflow_id="12345_wf",
        dag_id="12345_dagid",
        task_specs={
            "a": conn_spec.ExtractSpec(
                name="extract",
                type=enums.JobType.EXTRACT,
                storage_config=config.StorageConfig(
                    type=config.StorageType.File,
                    file_config=config.FileStorageConfig(
                        directory="/Users/saurav/.aqueduct/server/storage"
                    ),
                ),
                metadata_path="extrat_meta",
                connector_name=common.Name.POSTGRES,
                connector_config={
                    "conf": {
                        "username": "user",
                        "password": "pwd",
                        "database": "db",
                        "host": "localhost",
                    }
                },
                parameters=extract.RelationalParams(query="SELECT * FROM table;"),
                input_param_names=[],
                input_content_paths=[],
                input_metadata_paths=[],
                output_content_path="output_content",
                output_metadata_path="output_metadata",
            ),
            "b": func_spec.FunctionSpec(
                name="func",
                type=enums.JobType.FUNCTION,
                storage_config=config.StorageConfig(
                    type=config.StorageType.File,
                    file_config=config.FileStorageConfig(
                        directory="/Users/saurav/.aqueduct/server/storage"
                    ),
                ),
                metadata_path="func_metadata",
                function_path="func_path",
                function_extract_path="func_extract_path",
                entry_point_file="entry_file",
                entry_point_class="entry_class",
                entry_point_method="entry_method",
                custom_args="{}",
                input_content_paths=["input1", "input2"],
                input_metadata_paths=["meta1", "meta2"],
                output_content_paths=["output1"],
                output_metadata_paths=["output_meta1"],
                input_artifact_types=[enums.InputArtifactType.TABLE, enums.InputArtifactType.TABLE],
                output_artifact_types=[enums.OutputArtifactType.TABLE],
            ),
        },
        task_edges={"a": "b"},
    )
    execute.run(aspec)


if __name__ == "__main__":
    main()
