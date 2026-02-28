"""Execute SPARQL queries against the Wikidata Query Service."""

import requests
from .sparql import ColumnMapping

WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "WikiSQL/0.2.0 (https://github.com/Emma-Leonhart/Wikidata-SQL)"


def execute_sparql(sparql: str) -> dict:
    """Run a SPARQL query and return the raw JSON response."""
    resp = requests.get(
        WIKIDATA_SPARQL_ENDPOINT,
        params={"query": sparql, "format": "json"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def _simplify_value(cell: dict) -> str:
    """Extract a human-readable value from a SPARQL result cell."""
    value = cell.get("value", "")
    if value.startswith("http://www.wikidata.org/entity/"):
        value = value.split("/")[-1]
    return value


def results_to_table(
    data: dict,
    column_map: list[ColumnMapping] | None = None,
) -> tuple[list[str], list[list[str]]]:
    """Convert SPARQL JSON results into (headers, rows) for tabular display.

    If column_map is provided, only the mapped columns are shown and headers
    are renamed to the user-friendly display names.
    """
    all_vars = data["head"]["vars"]

    if column_map:
        # Only show columns the user asked for, with renamed headers
        headers = [cm.display_name for cm in column_map]
        rows = []
        for binding in data["results"]["bindings"]:
            row = []
            for cm in column_map:
                cell = binding.get(cm.sparql_var, {})
                row.append(_simplify_value(cell))
            rows.append(row)
    else:
        # No mapping — show all columns as-is
        headers = list(all_vars)
        rows = []
        for binding in data["results"]["bindings"]:
            row = []
            for var in all_vars:
                cell = binding.get(var, {})
                row.append(_simplify_value(cell))
            rows.append(row)

    return headers, rows
