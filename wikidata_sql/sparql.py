"""Translate a WikiQuery into a SPARQL query string."""

from dataclasses import dataclass
from .parser import WikiQuery, Column, ColumnKind, Condition, JoinClause, WikiTable


@dataclass
class ColumnMapping:
    """Maps a SPARQL variable to the display name the user expects."""
    sparql_var: str    # e.g. "P17Label" or "P17" or "item"
    display_name: str  # e.g. "P17" or "P17_qid" or "country"


@dataclass
class SparqlResult:
    """A generated SPARQL query plus metadata for formatting output."""
    sparql: str
    column_map: list[ColumnMapping]


def _var(name: str) -> str:
    return f"?{name}"


def _table_var(table: WikiTable) -> str:
    return table.alias or "item"


def _prop_var(table_var: str, pid: str) -> str:
    if table_var == "item":
        return pid
    return f"{table_var}_{pid}"


def compile_query(query: WikiQuery, language: str = "en") -> SparqlResult:
    """Convert a parsed WikiQuery into a SPARQL query + column mappings."""

    main_var = _table_var(query.table)
    triples: list[str] = []
    optionals: list[str] = []
    filters: list[str] = []
    select_vars: list[str] = []
    column_map: list[ColumnMapping] = []

    # --- Main table triple ---
    triples.append(
        f"  {_var(main_var)} wdt:{query.table.property} wd:{query.table.qid} ."
    )

    # --- Collect all properties we need triples for ---
    needed_props: dict[str, tuple[str, str]] = {}  # key -> (pid, table_var)

    def _ensure_prop(pid: str, tvar: str) -> None:
        key = f"{tvar}.{pid}"
        if key not in needed_props:
            needed_props[key] = (pid, tvar)

    # --- Process columns ---
    has_star = any(c.kind == ColumnKind.STAR for c in query.columns)

    if has_star:
        select_vars.append(_var(main_var))
        select_vars.append(_var(f"{main_var}Label"))
        column_map.append(ColumnMapping(main_var, "item_qid"))
        column_map.append(ColumnMapping(f"{main_var}Label", "item"))
    else:
        for col in query.columns:
            if col.kind == ColumnKind.ITEM:
                select_vars.append(_var(f"{main_var}Label"))
                column_map.append(ColumnMapping(
                    f"{main_var}Label", col.alias or "item"))
            elif col.kind == ColumnKind.ITEM_QID:
                select_vars.append(_var(main_var))
                column_map.append(ColumnMapping(
                    main_var, col.alias or "item_qid"))
            elif col.kind == ColumnKind.LABEL:
                pvar = _prop_var(main_var, col.pid)
                _ensure_prop(col.pid, main_var)
                # Select both the entity var (so label service works) and its label
                if _var(pvar) not in select_vars:
                    select_vars.append(_var(pvar))
                label_var = f"{pvar}Label"
                if _var(label_var) not in select_vars:
                    select_vars.append(_var(label_var))
                column_map.append(ColumnMapping(
                    label_var, col.alias or col.pid))
            elif col.kind == ColumnKind.QID:
                pvar = _prop_var(main_var, col.pid)
                _ensure_prop(col.pid, main_var)
                if _var(pvar) not in select_vars:
                    select_vars.append(_var(pvar))
                column_map.append(ColumnMapping(
                    pvar, col.alias or f"{col.pid}_qid"))

    # --- JOIN tables ---
    join_counter = 0
    for join in query.joins:
        # Ensure join table has a distinct variable name
        if join.table.alias:
            jvar = join.table.alias
        else:
            join_counter += 1
            jvar = f"j{join_counter}"
            join.table.alias = jvar

        triples.append(
            f"  {_var(jvar)} wdt:{join.table.property} wd:{join.table.qid} ."
        )

        # Parse ON references — "table.P17" or just "P17"
        # Left defaults to main table, right defaults to join table
        left_ref = join.on_left
        right_ref = join.on_right

        left_tvar, left_pid = _parse_on_ref(left_ref, main_var)
        right_tvar, right_pid = _parse_on_ref(right_ref, jvar)

        # Add triples for both sides of the ON
        left_pvar = _prop_var(left_tvar, left_pid)
        right_pvar = _prop_var(right_tvar, right_pid)

        triples.append(f"  {_var(left_tvar)} wdt:{left_pid} {_var(left_pvar)} .")
        triples.append(f"  {_var(right_tvar)} wdt:{right_pid} {_var(right_pvar)} .")

        if left_pvar != right_pvar:
            filters.append(f"  FILTER({_var(left_pvar)} = {_var(right_pvar)})")

    # --- WHERE conditions ---
    # Track which properties are constrained by WHERE (so they become non-optional)
    where_constrained: set[str] = set()

    for cond in query.conditions:
        _ensure_prop(cond.pid, main_var)
        pvar = _prop_var(main_var, cond.pid)

        if cond.is_qid_col:
            where_constrained.add(cond.pid)
            if cond.op.value == "=":
                val = cond.value.upper()
                if val.startswith("Q"):
                    # Bind the variable so it's available for SELECT/labels
                    triples.append(f"  {_var(main_var)} wdt:{cond.pid} {_var(pvar)} .")
                    filters.append(f"  FILTER({_var(pvar)} = wd:{val})")
                else:
                    triples.append(f"  {_var(main_var)} wdt:{cond.pid} {_var(pvar)} .")
                    filters.append(
                        f'  FILTER(STR({_var(pvar)}) = "{cond.value}")')
            elif cond.op.value == "!=":
                val = cond.value.upper()
                triples.append(f"  {_var(main_var)} wdt:{cond.pid} {_var(pvar)} .")
                if val.startswith("Q"):
                    filters.append(f"  FILTER({_var(pvar)} != wd:{val})")
                else:
                    filters.append(
                        f'  FILTER(STR({_var(pvar)}) != "{cond.value}")')
        else:
            # Label-based filter: make the property non-optional and do
            # explicit rdfs:label lookup so FILTER can see the value
            where_constrained.add(cond.pid)
            label_var = f"{pvar}_label"
            triples.append(f"  {_var(main_var)} wdt:{cond.pid} {_var(pvar)} .")
            triples.append(f'  {_var(pvar)} rdfs:label {_var(label_var)} .')
            triples.append(f'  FILTER(LANG({_var(label_var)}) = "{language}")')
            sparql_op = cond.op.value
            filters.append(
                f'  FILTER({_var(label_var)} = "{cond.value}"@{language})'
                if sparql_op == "="
                else f'  FILTER({_var(label_var)} {sparql_op} "{cond.value}"@{language})'
            )

    # --- Build property triples ---
    seen_props = set()
    for key, (pid, tvar) in needed_props.items():
        if key in seen_props:
            continue
        seen_props.add(key)
        pvar = _prop_var(tvar, pid)

        # Skip if WHERE already added a direct triple for this property
        if pid in where_constrained:
            continue

        optionals.append(f"  OPTIONAL {{ {_var(tvar)} wdt:{pid} {_var(pvar)} . }}")

    # --- Label service ---
    label_service = (
        f'  SERVICE wikibase:label {{ bd:serviceParam wikibase:language '
        f'"[AUTO_LANGUAGE],{language}" . }}'
    )

    # --- Assemble ---
    select_str = " ".join(select_vars)
    lines = [f"SELECT {select_str} WHERE {{"]
    lines.extend(triples)
    lines.extend(optionals)
    lines.extend(filters)
    lines.append(label_service)
    lines.append("}")

    if query.order_by:
        order_terms = []
        for term in query.order_by:
            tu = term.upper()
            if tu.endswith(" ASC"):
                order_terms.append(f"ASC({_var(term[:-4].strip())})")
            elif tu.endswith(" DESC"):
                order_terms.append(f"DESC({_var(term[:-5].strip())})")
            else:
                order_terms.append(_var(term))
        lines.append("ORDER BY " + " ".join(order_terms))

    if query.limit is not None:
        lines.append(f"LIMIT {query.limit}")

    return SparqlResult(sparql="\n".join(lines), column_map=column_map)


def to_sparql(query: WikiQuery, language: str = "en") -> str:
    """Convenience: just return the SPARQL string."""
    return compile_query(query, language).sparql


def _parse_on_ref(ref: str, default_tvar: str) -> tuple[str, str]:
    """Parse a JOIN ON reference into (table_var, property_id).

    'shrines.P17' -> ('shrines', 'P17')
    'P17'         -> (default_tvar, 'P17')
    """
    if "." in ref:
        tbl, col = ref.split(".", 1)
        return tbl, col.upper()
    return default_tvar, ref.upper()
