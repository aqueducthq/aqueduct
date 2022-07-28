import json
import uuid

from aqueduct.artifact import Artifact, ArtifactSpec
from aqueduct.dag import DAG, Metadata
from aqueduct.enums import (
    ExecutionStatus,
    FunctionGranularity,
    FunctionType,
    GoogleSheetsSaveMode,
    LoadUpdateMode,
    OperatorType,
    S3TabularFormat,
    SalesforceExtractType,
    ServiceType,
)
from aqueduct.operators import (
    ExtractSpec,
    FunctionSpec,
    GoogleSheetsExtractParams,
    GoogleSheetsLoadParams,
    LoadSpec,
    Operator,
    OperatorSpec,
    RelationalDBExtractParams,
    RelationalDBLoadParams,
    S3ExtractParams,
    S3LoadParams,
    SalesforceExtractParams,
    SalesforceLoadParams,
)
from aqueduct.responses import Logs, OperatorResult, PreviewResponse, TableArtifactResult
from aqueduct.tests.utils import _construct_dag, _construct_operator
from aqueduct.utils import generate_uuid


def test_artifact_serialization():
    artifact_id = uuid.uuid4()
    artifact_name = "Extract Artifact"
    extract_artifact = Artifact(id=artifact_id, name=artifact_name, spec=ArtifactSpec(table={}))

    assert extract_artifact.json() == json.dumps(
        {
            "id": str(artifact_id),
            "name": artifact_name,
            "spec": {"table": {}, "float": None, "bool": None, "jsonable": None},
        }
    )


def test_operator_serialization():
    op_id = uuid.uuid4()
    other_ids = [uuid.uuid4(), uuid.uuid4()]
    fn_operator = Operator(
        id=op_id,
        name="Function Operator",
        description="",
        spec=OperatorSpec(
            function=FunctionSpec(
                type=FunctionType.FILE,
                granularity=FunctionGranularity.TABLE,
            )
        ),
        inputs=[other_ids[0]],
        outputs=[other_ids[1]],
        function_file_path="function.zip",
    )
    assert fn_operator.json(exclude_none=True) == json.dumps(
        {
            "id": str(op_id),
            "name": "Function Operator",
            "description": "",
            "spec": {
                "function": {
                    "type": FunctionType.FILE,
                    "granularity": FunctionGranularity.TABLE,
                    "language": "Python",
                },
            },
            "inputs": [str(other_ids[0])],
            "outputs": [str(other_ids[1])],
        }
    )


def test_preview_response_loading():
    op_id = uuid.uuid4()
    op_result = OperatorResult(
        status=ExecutionStatus.SUCCEEDED,
        user_logs=Logs(stdout="These are the operator logs"),
    )
    artifact_id = uuid.uuid4()
    artifact_result = TableArtifactResult(
        table_schema=[{"Col 1": "int"}, {"Col 2": "str"}],
        data=b"This is a serialized pandas dataframe",
    )
    preview_resp = {
        "status": ExecutionStatus.SUCCEEDED,
        "err_msg": "",
        "operator_results": {
            str(op_id): op_result,
        },
        "artifact_results": {
            str(artifact_id): artifact_result,
        },
    }

    assert PreviewResponse(**preview_resp) == PreviewResponse(
        status=ExecutionStatus.SUCCEEDED,
        operator_results={
            op_id: op_result,
        },
        artifact_results={
            artifact_id: artifact_result,
        },
    )


def test_excluded_fields_can_be_compared():
    op_id = generate_uuid()
    artifact_id = generate_uuid()

    op = _construct_operator(
        id=op_id,
        name="Extract",
        operator_type=OperatorType.EXTRACT,
        inputs=[],
        outputs=[artifact_id],
    )
    dag = _construct_dag(
        operators=[op],
        artifacts=[],
    )
    # Constructed DAG is missing the excluded field 'operator_by_name`
    assert dag != DAG(
        operators={**{str(op.id): op}},
        artifacts={},
        metadata=Metadata(),
    )

    # This is the correct comparison.
    assert dag == DAG(
        operators={**{str(op.id): op}},
        operator_by_name={**{op.name: op}},
        artifacts={},
        metadata=Metadata(),
    )


def test_extract_serialization():
    op_id = uuid.uuid4()
    other_ids = [uuid.uuid4(), uuid.uuid4()]
    integration_id = uuid.uuid4()
    extract_operator = Operator(
        id=op_id,
        name="Extract Operator",
        description="",
        spec=OperatorSpec(
            extract=ExtractSpec(
                service=ServiceType.POSTGRES,
                integration_id=integration_id,
                parameters=RelationalDBExtractParams(query="SELECT * FROM hotel_reviews;"),
            ),
        ),
        outputs=[other_ids[1]],
    )
    assert extract_operator.json(exclude_none=True) == json.dumps(
        {
            "id": str(op_id),
            "name": "Extract Operator",
            "description": "",
            "spec": {
                "extract": {
                    "service": ServiceType.POSTGRES,
                    "integration_id": str(integration_id),
                    "parameters": {
                        "query": "SELECT * FROM hotel_reviews;",
                    },
                }
            },
            "inputs": [],
            "outputs": [str(other_ids[1])],
        }
    )

    extract_operator_sf = Operator(
        id=op_id,
        name="Extract Operator Salesforce",
        description="",
        spec=OperatorSpec(
            extract=ExtractSpec(
                service=ServiceType.SALESFORCE,
                integration_id=integration_id,
                parameters=SalesforceExtractParams(
                    type=SalesforceExtractType.SEARCH, query="FIND joe;"
                ),
            ),
        ),
        outputs=[other_ids[1]],
    )
    assert extract_operator_sf.json(exclude_none=True) == json.dumps(
        {
            "id": str(op_id),
            "name": "Extract Operator Salesforce",
            "description": "",
            "spec": {
                "extract": {
                    "service": ServiceType.SALESFORCE,
                    "integration_id": str(integration_id),
                    "parameters": {
                        "type": "search",
                        "query": "FIND joe;",
                    },
                }
            },
            "inputs": [],
            "outputs": [str(other_ids[1])],
        }
    )

    extract_operator_gs = Operator(
        id=op_id,
        name="Extract Operator Google Sheets",
        description="",
        spec=OperatorSpec(
            extract=ExtractSpec(
                service=ServiceType.GOOGLE_SHEETS,
                integration_id=integration_id,
                parameters=GoogleSheetsExtractParams(spreadsheet_id="0"),
            ),
        ),
        outputs=[other_ids[1]],
    )
    assert extract_operator_gs.json(exclude_none=True) == json.dumps(
        {
            "id": str(op_id),
            "name": "Extract Operator Google Sheets",
            "description": "",
            "spec": {
                "extract": {
                    "service": ServiceType.GOOGLE_SHEETS,
                    "integration_id": str(integration_id),
                    "parameters": {
                        "spreadsheet_id": "0",
                    },
                }
            },
            "inputs": [],
            "outputs": [str(other_ids[1])],
        }
    )

    extract_operator_s3 = Operator(
        id=op_id,
        name="Extract Operator S3",
        description="",
        spec=OperatorSpec(
            extract=ExtractSpec(
                service=ServiceType.S3,
                integration_id=integration_id,
                parameters=S3ExtractParams(
                    filepath=json.dumps("test.csv"),
                    format=S3TabularFormat.CSV,
                ),
            ),
        ),
        outputs=[other_ids[1]],
    )
    assert extract_operator_s3.json(exclude_none=True) == json.dumps(
        {
            "id": str(op_id),
            "name": "Extract Operator S3",
            "description": "",
            "spec": {
                "extract": {
                    "service": ServiceType.S3,
                    "integration_id": str(integration_id),
                    "parameters": {
                        "filepath": json.dumps("test.csv"),
                        "format": "CSV",
                    },
                }
            },
            "inputs": [],
            "outputs": [str(other_ids[1])],
        }
    )


def test_load_serialization():
    op_id = uuid.uuid4()
    other_ids = [uuid.uuid4(), uuid.uuid4()]
    integration_id = uuid.uuid4()
    load_operator = Operator(
        id=op_id,
        name="Load Operator",
        description="",
        spec=OperatorSpec(
            load=LoadSpec(
                service=ServiceType.POSTGRES,
                integration_id=integration_id,
                parameters=RelationalDBLoadParams(
                    table="hotel_reviews", update_mode=LoadUpdateMode.REPLACE
                ),
            ),
        ),
        inputs=[other_ids[0]],
    )
    assert load_operator.json(exclude_none=True) == json.dumps(
        {
            "id": str(op_id),
            "name": "Load Operator",
            "description": "",
            "spec": {
                "load": {
                    "service": ServiceType.POSTGRES,
                    "integration_id": str(integration_id),
                    "parameters": {
                        "table": "hotel_reviews",
                        "update_mode": "replace",
                    },
                }
            },
            "inputs": [str(other_ids[0])],
            "outputs": [],
        }
    )

    load_operator_sf = Operator(
        id=op_id,
        name="Load Operator Salesforce",
        description="",
        spec=OperatorSpec(
            load=LoadSpec(
                service=ServiceType.SALESFORCE,
                integration_id=integration_id,
                parameters=SalesforceLoadParams(object="hotel_reviews"),
            ),
        ),
        inputs=[other_ids[0]],
    )
    assert load_operator_sf.json(exclude_none=True) == json.dumps(
        {
            "id": str(op_id),
            "name": "Load Operator Salesforce",
            "description": "",
            "spec": {
                "load": {
                    "service": ServiceType.SALESFORCE,
                    "integration_id": str(integration_id),
                    "parameters": {
                        "object": "hotel_reviews",
                    },
                }
            },
            "inputs": [str(other_ids[0])],
            "outputs": [],
        }
    )

    load_operator_gs = Operator(
        id=op_id,
        name="Load Operator Google Sheets",
        description="",
        spec=OperatorSpec(
            load=LoadSpec(
                service=ServiceType.GOOGLE_SHEETS,
                integration_id=integration_id,
                parameters=GoogleSheetsLoadParams(
                    filepath="test_sheet.csv", save_mode=GoogleSheetsSaveMode.OVERWRITE
                ),
            ),
        ),
        inputs=[other_ids[0]],
    )
    assert load_operator_gs.json(exclude_none=True) == json.dumps(
        {
            "id": str(op_id),
            "name": "Load Operator Google Sheets",
            "description": "",
            "spec": {
                "load": {
                    "service": ServiceType.GOOGLE_SHEETS,
                    "integration_id": str(integration_id),
                    "parameters": {
                        "filepath": "test_sheet.csv",
                        "save_mode": "overwrite",
                    },
                }
            },
            "inputs": [str(other_ids[0])],
            "outputs": [],
        }
    )

    load_operator_s3 = Operator(
        id=op_id,
        name="Load Operator S3",
        description="",
        spec=OperatorSpec(
            load=LoadSpec(
                service=ServiceType.S3,
                integration_id=integration_id,
                parameters=S3LoadParams(
                    filepath="test.json",
                    format=S3TabularFormat.JSON,
                ),
            ),
        ),
        inputs=[other_ids[0]],
    )
    print(load_operator_s3.json(exclude_none=True))
    assert load_operator_s3.json(exclude_none=True) == json.dumps(
        {
            "id": str(op_id),
            "name": "Load Operator S3",
            "description": "",
            "spec": {
                "load": {
                    "service": ServiceType.S3,
                    "integration_id": str(integration_id),
                    "parameters": {
                        "filepath": "test.json",
                        "format": S3TabularFormat.JSON,
                    },
                }
            },
            "inputs": [str(other_ids[0])],
            "outputs": [],
        }
    )
