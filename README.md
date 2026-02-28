# Wikidata-SQL

Run SQL queries against Wikidata. Instead of writing SPARQL, write familiar SQL using Wikidata Q-IDs as table names.

## Install

```bash
pip install WikiSQL
```

## Quick Start

```bash
wikisql                                          # interactive REPL
wikisql "SELECT * FROM Q845945 LIMIT 10"         # single query
wikisql --sparql "SELECT * FROM Q845945 LIMIT 10" # show generated SPARQL
wikisql -l ja "SELECT * FROM Q845945 LIMIT 10"   # Japanese labels
```

## How It Works

A Q-ID in the `FROM` clause creates a virtual table of all entities with that class:

```sql
-- All Shinto shrines (instances of Q845945)
SELECT * FROM Q845945 LIMIT 10;

-- Subclasses of Shinto shrine (P279 instead of default P31)
SELECT * FROM P279:Q845945 LIMIT 10;
```

## Selecting Properties

Use Wikidata property IDs as column names. By default, values show human-readable **labels**:

```sql
-- Show country and population of cities
SELECT item, P17, P1082 FROM Q515 LIMIT 5;
```

| item    | P17            | P1082  |
|---------|----------------|--------|
| Vianen  | Netherlands    | 19967  |
| Mysore  | India          |        |
| Belfast | United Kingdom | 345006 |

Append `_qid` to get the raw Wikidata entity ID instead:

```sql
SELECT P17, P17_qid FROM Q515 LIMIT 3;
```

| P17           | P17_qid |
|---------------|---------|
| United States | Q30     |
| Switzerland   | Q39     |

## WHERE Filtering

Filter by **label** (human-readable name):

```sql
SELECT item, P17 FROM Q515 WHERE P17 = 'France' LIMIT 5;
```

Filter by **QID** (entity ID):

```sql
SELECT item, P17 FROM Q515 WHERE P17_qid = 'Q142' LIMIT 5;
```

## JOINs

Join two virtual tables on a shared property:

```sql
SELECT * FROM Q845945 s JOIN Q5 p ON s.P17 = p.P27 LIMIT 5;
```

## Column Reference

| Column     | Shows                      | Example output |
|------------|----------------------------|----------------|
| `*`        | Entity QID + label         | Q60, New York City |
| `item`     | Entity label               | New York City  |
| `item_qid` | Entity QID                | Q60            |
| `P17`      | Property value label       | Japan          |
| `P17_qid`  | Property value QID         | Q17            |

## REPL Commands

- `\sparql` - Toggle SPARQL display on/off
- `\q` / `quit` / `exit` - Exit
