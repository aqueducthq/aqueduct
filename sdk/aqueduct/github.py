from typing import List, Optional, Tuple

from aqueduct.enums import FunctionGranularity, FunctionType, GithubRepoConfigContentType
from aqueduct.error import InvalidGithubQueryError
from aqueduct.table_artifact import TableArtifact
from aqueduct.templates import DEFAULT_OP_METHOD_NAME
from aqueduct.utils import MODEL_FILE_NAME

from aqueduct import api_client

from .decorator import OutputArtifactFunction, wrap_spec
from .operators import (
    EntryPoint,
    FunctionSpec,
    GithubMetadata,
    OperatorSpec,
    RelationalDBExtractParams,
)


def _get_operator_name(prefix: str, repo_url: str, branch: str, path: str) -> str:
    return f"{prefix}_{repo_url}_{branch}_{path}".replace("/", "_")


# split repo url 'owner/repo' to separate strings 'owner' and 'repo'
def _get_owner_and_repo_from_url(repo_url: str) -> Tuple[str, str]:
    splitted = repo_url.split("/")
    if len(splitted) != 2:
        raise Exception("Specified github repository must follow format '<owner>/<repo>'")

    return splitted[0], splitted[1]


class Github:
    def __init__(self, repo_url: str, branch: str = ""):
        self.repo_url = repo_url
        self.branch = branch

    def _get_function_spec(
        self,
        repo_url: str,
        branch: str,
        path: Optional[str],
        entry_point_file: Optional[str],
        entry_point_class: Optional[str],
        entry_point_method: Optional[str],
        repo_config_content_name: Optional[str],
    ) -> FunctionSpec:
        repo_config_content_type = (
            GithubRepoConfigContentType.OPERATOR if repo_config_content_name else None
        )
        owner, repo = _get_owner_and_repo_from_url(repo_url)
        return FunctionSpec(
            type=FunctionType.GITHUB,
            granularity=FunctionGranularity.TABLE,
            github_metadata=GithubMetadata(
                owner=owner,
                repo=repo,
                branch=branch,
                path=path,
                repo_config_content_name=repo_config_content_name,
                repo_config_content_type=repo_config_content_type,
            ),
            entry_point=EntryPoint(
                file=entry_point_file,
                class_name=entry_point_class,
                method=entry_point_method,
            ),
        )

    def checkout(self, branch: str) -> None:
        self.branch = branch

    def list_branches(self) -> List[str]:
        return api_client.__GLOBAL_API_CLIENT__.list_github_branches(self.repo_url)

    def op(
        self,
        path: Optional[str] = None,
        entry_point: str = MODEL_FILE_NAME,
        class_name: Optional[str] = None,
        method: str = DEFAULT_OP_METHOD_NAME,
        op_name: Optional[str] = None,
    ) -> OutputArtifactFunction:
        """
        Creates an operator from a python function specified in a github repo.

        *Does not currently support checks or metrics*

        Args:
            path:
                The relative directory path containing the entire function and any of its dependencies (e.g. utils methods).
                Default to empty string which stands for using the entire repo.

            entry_point:
                The relative path, to the directory specified by `path`, of the function's entry point.
                Default to `model.py` if not specified.

            class_name:
                The class name of the operator.
                If not specified, it will default to `Function`.
                If specified as empty string, the method will be directly imported from the `entry_point_file`.

            method:
                The method to run on artifacts as the operator.
                If `class_name` is specified, we first construct the class
                and call `.<method>(inputs)` of the object.
                If `class_name` is empty string, we import `<method>` from
                `<entry_point>`, and call the method over inputs directly.

                Default to `predict` if not specified.

                See `Example` below for more details.

            op_name:
                The operator name in the repo's `.aqconfig` field. This will override all other arguments.
                Follow `examples/.aqconfig.example` for more details.

        Returns:
            An python opertor that can be called over artifacts.

        Example:
            Assuming a github repo structure:
            /models
                /churn
                    /configs
                        churn_prams.json
                    /python
                        utils.py
                        function.py: ```
                            class Churn:
                                def __init__(self):
                                    self.model = load_churn('../configs/churn_params.json') # load model

                                def run(self, input: pd.DataFrame):
                                    input['predicted'] = self.model.inference(input['review_features'])
                                    return input
                        ```
            Then to use it:
            ```
            gh = aqueduct_client.github(repo=<repo_name>, branch=<branch_name>)
            churn_op = gh.op(
                path="models/churn",
                entry_point="python/function.py",
                class_name="Churn",
                method="run",
            )
            predicted = churn_op(upstream_artifacts) # just like a python operator
            ```
        """
        function_spec = self._get_function_spec(
            self.repo_url,
            self.branch,
            path,
            entry_point,
            class_name,
            method,
            op_name,
        )

        def wrapped(*inputs: TableArtifact) -> TableArtifact:
            new_function_artifact = wrap_spec(
                OperatorSpec(function=function_spec),
                *inputs,
                op_name=_get_operator_name(
                    "github_function", self.repo_url, self.branch, path or ""
                ),
            )
            assert isinstance(new_function_artifact, TableArtifact)
            return new_function_artifact

        return wrapped

    def query(
        self, path: Optional[str] = None, query_name: Optional[str] = None
    ) -> RelationalDBExtractParams:
        """
        Creates an query specified in a github repo, by either `path` or `query_name`.
        `query_name` will override `path` if specified.

        Args:
            path:
                The relative directory path containing the single file specifying the query.

            query_name:
                The query name in the repo's `.aqueduct.config` field. This will override `path`.
                Follow `examples/.aqueduct.config.example` for more details.

        Returns:
            A query object. For now, it can be used for relational DB connection queries.

        Example:
            Assuming a github repo structure:
            ```
            /queries
                hotels.sql
            ```
            Then to use it:
            ```
            warehouse = aqueduct_client.integration(name="aqueduct_demo")
            gh = aqueduct_client.github(repo=<repo_name>, branch=<branch_name>)
            reviews = warehouse.sql(
                query=gh.query(path="queries/hotel.sql")
            )
            ```
        """
        repo_config_content_type = GithubRepoConfigContentType.QUERY if query_name else None

        if not path and not query_name:
            raise InvalidGithubQueryError(
                "For query from github, you must specify either a path to query file, or a query_name defined by `queries` section of .aqconfig."
            )
        owner, repo = _get_owner_and_repo_from_url(self.repo_url)
        return RelationalDBExtractParams(
            github_metadata=GithubMetadata(
                owner=owner,
                repo=repo,
                branch=self.branch,
                path=path,
                repo_config_content_name=query_name,
                repo_config_content_type=repo_config_content_type,
            )
        )
