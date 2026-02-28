"""Command-line interface for WikiSQL."""

import sys
from tabulate import tabulate
from .parser import parse
from .sparql import compile_query
from .client import execute_sparql, results_to_table


def run_query(sql: str, language: str = "en", show_sparql: bool = False) -> None:
    """Parse, translate, execute, and display a WikiSQL query."""
    query = parse(sql)
    result = compile_query(query, language=language)

    if show_sparql:
        print("\n--- Generated SPARQL ---")
        print(result.sparql)
        print("------------------------\n")

    data = execute_sparql(result.sparql)
    headers, rows = results_to_table(data, column_map=result.column_map)

    if not rows:
        print("(no results)")
        return

    print(tabulate(rows, headers=headers, tablefmt="simple"))
    print(f"\n({len(rows)} rows)")


def repl(language: str = "en", show_sparql: bool = False) -> None:
    """Interactive WikiSQL REPL."""
    print("WikiSQL - SQL interface to Wikidata")
    print("Type a SQL query, or 'quit' to exit.")
    print("Example: SELECT * FROM Q845945 LIMIT 10;")
    print()

    while True:
        try:
            sql = input("wikisql> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not sql:
            continue
        if sql.lower() in ("quit", "exit", "\\q"):
            break
        if sql.lower() == "\\sparql":
            show_sparql = not show_sparql
            print(f"SPARQL display: {'ON' if show_sparql else 'OFF'}")
            continue

        try:
            run_query(sql, language=language, show_sparql=show_sparql)
        except Exception as e:
            print(f"Error: {e}")
        print()


def _ensure_utf8_stdout() -> None:
    """Reconfigure stdout/stderr to UTF-8 so Unicode labels render on Windows."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    _ensure_utf8_stdout()
    import argparse
    ap = argparse.ArgumentParser(description="Run SQL queries against Wikidata")
    ap.add_argument("query", nargs="?", help="SQL query to execute (omit for REPL)")
    ap.add_argument("-l", "--language", default="en", help="Language for labels (default: en)")
    ap.add_argument("--sparql", action="store_true", help="Show generated SPARQL")
    args = ap.parse_args()

    if args.query:
        try:
            run_query(args.query, language=args.language, show_sparql=args.sparql)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        repl(language=args.language, show_sparql=args.sparql)


if __name__ == "__main__":
    main()
