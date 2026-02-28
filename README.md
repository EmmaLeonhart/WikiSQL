# Wikidata-SQL

Run SQL queries against Wikidata. Instead of writing SPARQL, write familiar SQL using Wikidata Q-IDs as table names.

## Quick Start

```bash
pip install -e .
wikisql
```

## How It Works

A Q-ID in the `FROM` clause creates a virtual table of all entities with that class:

```sql
-- All Shinto shrines (instances of Q845945)
SELECT * FROM Q845945 LIMIT 10;
```

This translates to:
```sparql
SELECT ?item ?itemLabel WHERE {
  ?item wdt:P31 wd:Q845945 .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en" . }
}
LIMIT 10
```

### Custom Properties

By default, `FROM Q...` uses P31 (instance of). Prefix with a property to change this:

```sql
-- Subclasses of Shinto shrine
SELECT * FROM P279:Q845945 LIMIT 10;
```

## Usage

**Interactive REPL:**
```bash
wikisql
```

**Single query:**
```bash
wikisql "SELECT * FROM Q845945 LIMIT 10"
```

**Show generated SPARQL:**
```bash
wikisql --sparql "SELECT * FROM Q845945 LIMIT 10"
```

**Change label language:**
```bash
wikisql -l ja "SELECT * FROM Q845945 LIMIT 10"
```

## REPL Commands

- `\sparql` - Toggle SPARQL display on/off
- `\q` / `quit` / `exit` - Exit
