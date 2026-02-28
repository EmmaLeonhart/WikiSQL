# Wikidata-SQL

## Workflow Rules
- **Commit early and often.** Every meaningful change gets a commit with a clear message explaining *why*, not just what.
- **Do not enter planning-only modes.** All thinking must produce files and commits. If scope is unclear, create a `planning/` directory and write `.md` files there instead of using an internal planning mode.
- **Keep this file up to date.** As the project takes shape, record architectural decisions, conventions, and anything needed to work effectively in this repo.
- **Update README.md regularly.** It should always reflect the current state of the project for human readers.

## Project Description
SQL-to-SPARQL translator for Wikidata. Users write SQL with Q-IDs as table names, and the tool translates to SPARQL, executes against the Wikidata Query Service, and displays results.

## Architecture and Conventions
- **Language:** Python 3.13
- **Package:** `wikidata_sql/` (installed as `wikisql` CLI)
- **Parser:** Custom regex-based parser in `parser.py` - extracts WikiTable references (Q-IDs with optional P: prefix) and standard SQL clauses
- **SPARQL Generator:** `sparql.py` - converts `WikiQuery` dataclass into SPARQL query strings
- **Client:** `client.py` - executes SPARQL against `query.wikidata.org/sparql` and formats results
- **CLI:** `cli.py` - argparse-based CLI with interactive REPL mode
- **Key convention:** No property prefix means P31 (instance of). `P279:Q845945` means "subclass of Shinto shrine".

# currentDate
Today's date is 2026-02-28.
