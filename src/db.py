"""SQLite helpers: connections, building the database, running queries and parsing sql/queries.sql."""
import re
import sqlite3
from pathlib import Path

import pandas as pd

import config


def connect(path=None):
    conn = sqlite3.connect(path or config.DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql, params=(), path=None):
    with connect(path) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def build(tables, path=None):
    """Create the schema and load the cleaned tables. Returns {table: row count}."""
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    with connect(path) as conn:
        conn.executescript(config.SCHEMA_PATH.read_text())
        for name in config.TABLE_ORDER:
            df = tables[name].astype(object).where(tables[name].notna(), None)
            cols = list(df.columns)
            conn.executemany(
                f"INSERT INTO {name} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                df.itertuples(index=False, name=None))
        conn.commit()
        conn.execute("VACUUM")
        return {name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in config.TABLE_ORDER}


def integrity_report(path=None):
    """Foreign-key violations and SQLite's own integrity check."""
    with connect(path) as conn:
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
    return {"foreign_key_violations": len(fk), "integrity_check": ok}


def table_columns(table, path=None):
    """[(name, type, notnull, pk)] for a table, from PRAGMA table_info."""
    with connect(path) as conn:
        return [(r[1], r[2], bool(r[3]), bool(r[5])) for r in conn.execute(f"PRAGMA table_info({table})")]


def primary_key(table, path=None):
    return next(name for name, _, _, pk in table_columns(table, path) if pk)


# ---------------------------------------------------------------- sql/queries.sql
_HEADER = re.compile(r"^-- name:\s*(?P<id>Q\d+)\s*\|\s*(?P<category>[^|]+)\|\s*(?P<question>.+)$")


def load_queries(path=None):
    """Parse sql/queries.sql into a list of dicts: id, category, question, chart, insight, sql.

    Each query starts with a header line
        -- name: Q01 | Property & Pricing | What is the average listing price by city?
    followed by an optional one-line finding and chart hint
        -- insight: New York is the priciest city ...
        -- chart: bar x=city y=avg_list_price
    """
    text = Path(path or config.QUERIES_PATH).read_text()
    queries, current = [], None
    for line in text.splitlines():
        header = _HEADER.match(line.strip())
        if header:
            current = {k: v.strip() for k, v in header.groupdict().items()}
            current.update(chart=None, insight="", sql_lines=[])
            queries.append(current)
        elif current is not None and line.strip().startswith(("-- chart:", "-- insight:")):
            key, value = line.strip()[3:].split(":", 1)
            current[key] = value.strip()
        elif current is not None and not line.startswith("-- ===="):   # skip section banners
            current["sql_lines"].append(line)
    for q in queries:
        q["sql"] = "\n".join(q.pop("sql_lines")).strip().rstrip(";").strip()
    return queries


def parse_chart(hint):
    """'bar x=city y=avg_price color=type' -> ('bar', {'x': 'city', 'y': 'avg_price', 'color': 'type'})"""
    if not hint:
        return None, {}
    kind, *pairs = hint.split()
    return kind, dict(p.split("=", 1) for p in pairs)
