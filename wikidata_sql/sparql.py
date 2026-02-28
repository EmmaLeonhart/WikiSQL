"""Translate a WikiQuery into a SPARQL query string."""

from .parser import WikiQuery


def to_sparql(query: WikiQuery, language: str = "en") -> str:
    """Convert a parsed WikiQuery into a SPARQL query for Wikidata."""

    table = query.table
    # Variable name for the main entity
    var = table.alias or "item"

    # Build the triple pattern: ?item wdt:P31 wd:Q845945 .
    body_lines = [
        f"  ?{var} wdt:{table.property} wd:{table.qid} ."
    ]

    # Build SELECT clause
    if query.columns == ["*"]:
        select_vars = f"?{var} ?{var}Label"
    else:
        select_parts = []
        for col in query.columns:
            if col.lower() == var.lower():
                select_parts.append(f"?{var}")
            elif col.lower() == f"{var}label":
                select_parts.append(f"?{var}Label")
            else:
                # Treat as a property - user used a column name
                # For now, include as-is with ? prefix
                select_parts.append(f"?{col}")
        select_vars = " ".join(select_parts)

    # Label service for human-readable labels
    body_lines.append(
        f'  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],{language}" . }}'
    )

    # Build SPARQL
    parts = [f"SELECT {select_vars} WHERE {{"]
    parts.extend(body_lines)
    parts.append("}")

    # ORDER BY
    if query.order_by:
        order_terms = []
        for term in query.order_by:
            # Handle ASC/DESC
            term_upper = term.upper()
            if term_upper.endswith(" ASC"):
                col = term[:-4].strip()
                order_terms.append(f"ASC(?{col})")
            elif term_upper.endswith(" DESC"):
                col = term[:-5].strip()
                order_terms.append(f"DESC(?{col})")
            else:
                order_terms.append(f"?{term}")
        parts.append("ORDER BY " + " ".join(order_terms))

    # LIMIT
    if query.limit is not None:
        parts.append(f"LIMIT {query.limit}")

    return "\n".join(parts)
