"""Execute SPARQL queries against the Wikidata Query Service."""

import requests

WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "WikidataSQL/0.1 (https://github.com/ericr/Wikidata-SQL)"


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


def results_to_table(data: dict) -> tuple[list[str], list[list[str]]]:
    """Convert SPARQL JSON results into (headers, rows) for tabular display.

    Returns simplified values: for URIs, extracts the Q-ID; for literals,
    returns the value string.
    """
    head = data["head"]["vars"]
    rows = []
    for binding in data["results"]["bindings"]:
        row = []
        for var in head:
            cell = binding.get(var, {})
            value = cell.get("value", "")
            # Shorten Wikidata entity URIs to Q-IDs
            if value.startswith("http://www.wikidata.org/entity/"):
                value = value.split("/")[-1]
            row.append(value)
        rows.append(row)
    return head, rows
