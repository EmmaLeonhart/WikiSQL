"""Parse WikiSQL queries into an intermediate representation."""

import re
from dataclasses import dataclass, field
from enum import Enum, auto


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class ColumnKind(Enum):
    """How a selected column should be rendered."""
    STAR = auto()       # SELECT *
    LABEL = auto()      # P17  -> show human-readable label
    QID = auto()        # P17_qid -> show raw Q-ID
    ITEM = auto()       # the entity itself (item / itemLabel)
    ITEM_QID = auto()   # item_qid -> raw entity QID


@dataclass
class Column:
    """A column in the SELECT clause."""
    kind: ColumnKind
    pid: str | None = None   # e.g. "P17" — None for STAR / ITEM
    alias: str | None = None # user-provided AS alias


class Op(Enum):
    EQ = "="
    NEQ = "!="
    LT = "<"
    GT = ">"
    LTE = "<="
    GTE = ">="


@dataclass
class Condition:
    """A single WHERE predicate: column op value."""
    column: str        # raw column name as written (e.g. "P17", "P17_qid")
    op: Op
    value: str         # the literal value (string or Q-ID)
    is_qid_col: bool   # True if column ended in _qid
    pid: str           # extracted property ID (e.g. "P17")


@dataclass
class WikiTable:
    """A virtual table derived from a Wikidata class."""
    property: str              # e.g. "P31"
    qid: str                   # e.g. "Q845945"
    alias: str | None = None   # SQL alias


@dataclass
class JoinClause:
    """A JOIN between two virtual tables."""
    table: WikiTable
    on_left: str    # left side of ON (column name)
    on_right: str   # right side of ON (column name)


@dataclass
class WikiQuery:
    """Parsed representation of a WikiSQL query."""
    columns: list[Column]
    table: WikiTable
    joins: list[JoinClause] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)
    limit: int | None = None
    order_by: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches: Q845945, P279:Q845945, etc.
TABLE_RE = re.compile(
    r"^(?:(?P<prop>P\d+):)?(?P<qid>Q\d+)$",
    re.IGNORECASE,
)

# Matches a P-ID column, optionally with _qid suffix
COLUMN_RE = re.compile(
    r"^(?P<pid>P\d+?)(?P<qid_suffix>_qid)?$",
    re.IGNORECASE,
)

# Matches comparison operators
OP_RE = re.compile(r"(!=|<=|>=|<|>|=)")


# ---------------------------------------------------------------------------
# Tokeniser helpers
# ---------------------------------------------------------------------------

def _parse_table(token: str) -> WikiTable:
    """Parse a table token like 'Q845945' or 'P279:Q845945'."""
    m = TABLE_RE.match(token)
    if not m:
        raise ValueError(
            f"Invalid table reference: {token!r}. "
            f"Expected Q-ID (e.g. Q845945) or P:Q (e.g. P279:Q845945)."
        )
    prop = (m.group("prop") or "P31").upper()
    qid = m.group("qid").upper()
    return WikiTable(property=prop, qid=qid)


def _parse_column(raw: str) -> Column:
    """Parse a single column token."""
    raw = raw.strip()

    if raw == "*":
        return Column(kind=ColumnKind.STAR)

    # Check for AS alias: "P17 AS country"
    alias = None
    as_match = re.match(r"(.+?)\s+AS\s+(\w+)", raw, re.IGNORECASE)
    if as_match:
        raw = as_match.group(1).strip()
        alias = as_match.group(2)

    # item / item_qid
    if raw.lower() == "item_qid":
        return Column(kind=ColumnKind.ITEM_QID, alias=alias)
    if raw.lower() == "item":
        return Column(kind=ColumnKind.ITEM, alias=alias)

    # P-ID columns
    m = COLUMN_RE.match(raw)
    if m:
        pid = m.group("pid").upper()
        if m.group("qid_suffix"):
            return Column(kind=ColumnKind.QID, pid=pid, alias=alias)
        else:
            return Column(kind=ColumnKind.LABEL, pid=pid, alias=alias)

    raise ValueError(
        f"Unknown column: {raw!r}. "
        f"Expected *, item, item_qid, or a property like P17 / P17_qid."
    )


def _parse_condition(text: str) -> Condition:
    """Parse a single condition like "P17 = 'Japan'" or "P17_qid = 'Q17'"."""
    text = text.strip()

    # Split on operator
    m = OP_RE.search(text)
    if not m:
        raise ValueError(f"No operator found in condition: {text!r}")

    col_raw = text[:m.start()].strip()
    op = Op(m.group(1))
    val_raw = text[m.end():].strip()

    # Strip quotes from value
    if (val_raw.startswith("'") and val_raw.endswith("'")) or \
       (val_raw.startswith('"') and val_raw.endswith('"')):
        val_raw = val_raw[1:-1]

    # Determine if it's a _qid column
    col_upper = col_raw.upper()
    if col_upper.endswith("_QID"):
        pid = col_upper[:-4]
        is_qid = True
    else:
        pid = col_upper
        is_qid = False

    # Validate it's a P-ID
    if not re.match(r"^P\d+$", pid):
        raise ValueError(
            f"WHERE column must be a property (P-ID): got {col_raw!r}"
        )

    return Condition(
        column=col_raw,
        op=op,
        value=val_raw,
        is_qid_col=is_qid,
        pid=pid,
    )


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def _split_respecting_quotes(text: str, delimiter: str = ",") -> list[str]:
    """Split text by delimiter but respect quoted strings."""
    parts = []
    current = []
    in_quote = None
    for char in text:
        if char in ("'", '"') and in_quote is None:
            in_quote = char
            current.append(char)
        elif char == in_quote:
            in_quote = None
            current.append(char)
        elif char == delimiter and in_quote is None:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def parse(sql: str) -> WikiQuery:
    """Parse a WikiSQL string into a WikiQuery."""
    sql = sql.strip().rstrip(";").strip()

    # ---- SELECT columns ----
    select_match = re.match(r"SELECT\s+(.+?)\s+FROM\s+", sql, re.IGNORECASE)
    if not select_match:
        raise ValueError(f"Could not parse SELECT ... FROM in: {sql}")

    columns_raw = select_match.group(1).strip()
    if columns_raw == "*":
        columns = [Column(kind=ColumnKind.STAR)]
    else:
        columns = [_parse_column(c) for c in _split_respecting_quotes(columns_raw)]

    # ---- FROM table ----
    rest = sql[select_match.end():]

    # Tokenise carefully: pull the table token, then optional alias, then keywords
    parts = re.split(r"\s+", rest, maxsplit=2)
    table = _parse_table(parts[0])

    remainder = ""
    if len(parts) > 1:
        next_upper = parts[1].upper()
        keywords = {"WHERE", "LIMIT", "ORDER", "GROUP", "HAVING", "JOIN",
                     "INNER", "LEFT", "RIGHT", "CROSS"}
        if next_upper == "AS" and len(parts) > 2:
            rest_parts = re.split(r"\s+", parts[2], maxsplit=1)
            table.alias = rest_parts[0]
            remainder = rest_parts[1] if len(rest_parts) > 1 else ""
        elif next_upper not in keywords:
            table.alias = parts[1]
            remainder = parts[2] if len(parts) > 2 else ""
        else:
            remainder = " ".join(parts[1:])

    # ---- JOINs ----
    joins = []
    join_pattern = re.compile(
        r"(?:INNER\s+)?JOIN\s+(\S+)"
        r"(?:\s+(?:AS\s+)?(\w+))?"
        r"\s+ON\s+(\w+(?:\.\w+)?)\s*=\s*(\w+(?:\.\w+)?)",
        re.IGNORECASE,
    )
    while True:
        jm = join_pattern.search(remainder)
        if not jm:
            break
        join_table = _parse_table(jm.group(1))
        if jm.group(2):
            join_table.alias = jm.group(2)
        joins.append(JoinClause(
            table=join_table,
            on_left=jm.group(3),
            on_right=jm.group(4),
        ))
        remainder = remainder[:jm.start()] + remainder[jm.end():]

    # ---- WHERE ----
    conditions = []
    where_match = re.search(
        r"\bWHERE\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|\s*$)",
        remainder, re.IGNORECASE,
    )
    if where_match:
        where_text = where_match.group(1).strip()
        # Split on AND (for now, only AND is supported)
        cond_parts = re.split(r"\s+AND\s+", where_text, flags=re.IGNORECASE)
        for part in cond_parts:
            conditions.append(_parse_condition(part))

    # ---- ORDER BY ----
    order_by = []
    order_match = re.search(
        r"\bORDER\s+BY\s+(.+?)(?:\s+LIMIT|\s*$)",
        remainder, re.IGNORECASE,
    )
    if order_match:
        order_by = [o.strip() for o in order_match.group(1).split(",")]

    # ---- LIMIT ----
    limit = None
    limit_match = re.search(r"\bLIMIT\s+(\d+)", remainder, re.IGNORECASE)
    if limit_match:
        limit = int(limit_match.group(1))

    return WikiQuery(
        columns=columns,
        table=table,
        joins=joins,
        conditions=conditions,
        limit=limit,
        order_by=order_by,
    )
