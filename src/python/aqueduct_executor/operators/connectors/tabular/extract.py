import re
from typing import Any, Optional, Union, Dict
from datetime import date
from aqueduct_executor.operators.connectors.tabular import common, models

# Regular Expression that matches any substring appearance with
# "{{ }}" and a word inside with optional space in front or after
# Potential Matches: "{{today}}", "{{ today  }}""
#
# Duplicated in the SDK at `sdk/aqueduct/integrations/sql_integration.py`.
# Make sure the two are in sync.
TAG_PATTERN = r"{{\s*[\w-]+\s*}}"


def replace_today() -> str:
    return "'" + date.today().strftime("%Y-%m-%d") + "'"


# A dictionary of built-in tags to their replacement string functions.
#
# Duplicated in spirit by the SDK at `sdk/aqueduct/integrations/sql_integration.py`.
# Make sure the two are in sync.
BUILT_IN_EXPANSIONS = {
    "today": replace_today,
}


class RelationalParams(models.BaseParams):
    # The query cannot be used until `apply_placeholders()` is called on it. This flushes out
    # any user-defined tags like `{{today}}`.
    query_is_usable: bool = False
    query: str

    # TODO: Consider not including github as part of relational params when it is JSON marshalled
    github_metadata: Optional[Any]

    def expand_placeholders(
        self,
        parameters: Dict[str, str],
    ) -> None:
        """Expands any tags found in the raw query, eg. {{ today }}.

        Relational queries can be arbitrarily parameterized the same way operators are. The only
        requirement is that these parameters must be defined as strings.

        User-defined parameters are prioritized over built-in ones. Eg. if the user defines a parameter
        named "today" that they set with value "1234", the "{{today}}" will be expanded as "1234", even
        though there already is a built-in expansion.
        """
        orig_query = self.query
        matches = re.findall(TAG_PATTERN, self.query)
        for match in matches:
            tag_name = match.strip(" {}")

            if tag_name in parameters:
                self.query = self.query.replace(match, parameters[tag_name])
            elif tag_name in BUILT_IN_EXPANSIONS:
                expansion_func = BUILT_IN_EXPANSIONS[tag_name]
                self.query = self.query.replace(match, expansion_func())
            else:
                # If there's a tag in the query for which no expansion value is available, we error here.
                raise Exception(
                    "Unable to expand tag `%s` for query `%s`." % (tag_name, orig_query)
                )

        print("Expanded query is `%s`." % self.query)
        self.query_is_usable = True

    def usable(self) -> bool:
        """Denotes whether all placeholders have already been expanded for this query.

        Callers should check that `usable()` -> True before actually executing this query.
        """
        return self.query_is_usable


class S3Params(models.BaseParams):
    filepath: str
    format: common.S3FileFormat


Params = Union[RelationalParams, S3Params]
