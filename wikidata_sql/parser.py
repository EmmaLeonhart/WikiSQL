"""Parse WikiSQL queries into an intermediate representation."""

import re
from dataclasses import dataclass, field


@dataclass
class WikiTable:
    """A virtual table derived from a Wikidata class.

    property: The property to use (default P31 = "instance of").
    qid: The Q-ID of the class (e.g. Q845945 for Shinto shrine).
    alias: Optional SQL alias for the table.
    """
    property: str
    qid: str
    alias: str | None = None


@dataclass
class WikiQuery:
    """Parsed representation of a WikiSQL query."""
    columns: list[str]          # ["*"] or list of column names
    table: WikiTable
    where: str | None = None    # raw WHERE clause (for future use)
    limit: int | None = None
    order_by: list[str] = field(default_factory=list)


# Matches: Q845945, P279:Q845945, etc.
TABLE_RE = re.compile(
    r"^(?:(?P<prop>P\d+):)?(?P<qid>Q\d+)$",
    re.IGNORECASE,
)


def parse(sql: str) -> WikiQuery:
    """Parse a WikiSQL string into a WikiQuery."""
    sql = sql.strip().rstrip(";").strip()

    # Extract columns (everything between SELECT and FROM)
    select_match = re.match(r"SELECT\s+(.+?)\s+FROM\s+", sql, re.IGNORECASE)
    if not select_match:
        raise ValueError(f"Could not parse SELECT ... FROM in: {sql}")

    columns_raw = select_match.group(1).strip()
    if columns_raw == "*":
        columns = ["*"]
    else:
        columns = [c.strip() for c in columns_raw.split(",")]

    # Extract the rest after FROM
    after_select = sql[select_match.end():]

    # The table reference is the next token (possibly with alias)
    # Split on whitespace, but stop at keywords
    parts = re.split(r"\s+", after_select, maxsplit=2)
    table_token = parts[0]

    # Parse the table token as a Wikidata reference
    table_match = TABLE_RE.match(table_token)
    if not table_match:
        raise ValueError(
            f"Invalid table reference: {table_token!r}. "
            f"Expected Q-ID (e.g. Q845945) or P:Q (e.g. P279:Q845945)."
        )

    prop = table_match.group("prop") or "P31"
    qid = table_match.group("qid").upper()

    # Check for alias and remaining clauses
    alias = None
    remainder = ""
    if len(parts) > 1:
        # Check if next token is a keyword or an alias
        next_token = parts[1].upper()
        keywords = {"WHERE", "LIMIT", "ORDER", "GROUP", "HAVING", "JOIN"}
        if next_token == "AS" and len(parts) > 2:
            # AS alias
            rest_parts = re.split(r"\s+", parts[2], maxsplit=1)
            alias = rest_parts[0]
            remainder = rest_parts[1] if len(rest_parts) > 1 else ""
        elif next_token not in keywords:
            # Implicit alias
            alias = parts[1]
            remainder = parts[2] if len(parts) > 2 else ""
        else:
            remainder = " ".join(parts[1:])

    # Parse LIMIT
    limit = None
    limit_match = re.search(r"\bLIMIT\s+(\d+)", remainder, re.IGNORECASE)
    if limit_match:
        limit = int(limit_match.group(1))

    # Parse ORDER BY
    order_by = []
    order_match = re.search(r"\bORDER\s+BY\s+(.+?)(?:\s+LIMIT|\s*$)", remainder, re.IGNORECASE)
    if order_match:
        order_by = [o.strip() for o in order_match.group(1).split(",")]

    # Parse WHERE
    where = None
    where_match = re.search(r"\bWHERE\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|\s*$)", remainder, re.IGNORECASE)
    if where_match:
        where = where_match.group(1).strip()

    return WikiQuery(
        columns=columns,
        table=WikiTable(property=prop.upper(), qid=qid, alias=alias),
        where=where,
        limit=limit,
        order_by=order_by,
    )
