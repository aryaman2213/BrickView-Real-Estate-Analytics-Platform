"""Data access for the dashboard: cached queries, the shared filter -> SQL WHERE builder, and CRUD."""
import re
import sqlite3
from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

import config
from src import db


# ---------------------------------------------------------------- reads
@st.cache_data(show_spinner=False)
def q(sql, params=()):
    """Cached read. Cleared after every write (see write())."""
    return db.query(sql, tuple(params))


def scalar(sql, params=()):
    frame = q(sql, params)
    return None if frame.empty else frame.iat[0, 0]


@st.cache_data(show_spinner=False)
def business_queries():
    return db.load_queries()


def run_readonly(sql):
    """Run a user-typed query on a read-only connection. Only one SELECT / WITH statement is allowed."""
    cleaned = re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql, flags=re.S).strip().rstrip(";").strip()
    if not re.match(r"(?is)^(select|with)\b", cleaned):
        raise ValueError("Only SELECT (or WITH ... SELECT) queries can be run here.")
    if ";" in cleaned:
        raise ValueError("Run one statement at a time.")
    uri = f"file:{config.DB_PATH}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        return pd.read_sql_query(cleaned, conn)


# ---------------------------------------------------------------- filters
@dataclass
class Filters:
    cities: list = field(default_factory=list)
    property_types: list = field(default_factory=list)
    price: tuple = (0, 0)
    price_bounds: tuple = (0, 0)
    agents: list = field(default_factory=list)
    date_field: str = "Listed date"
    dates: tuple = ()
    date_bounds: tuple = ()
    status: str = "All"
    bedrooms: list = field(default_factory=list)
    furnishing: list = field(default_factory=list)

    def where(self, alias=""):
        """Parameterised WHERE clause over v_listing_details (or anything with the same columns)."""
        p = f"{alias}." if alias else ""
        clauses, params = [], []

        def isin(column, values):
            if values:
                clauses.append(f"{p}{column} IN ({','.join('?' * len(values))})")
                params.extend(values)

        isin("city", self.cities)
        isin("property_type", self.property_types)
        isin("agent_id", self.agents)
        isin("bedrooms", self.bedrooms)
        isin("furnishing_status", self.furnishing)
        if self.price != self.price_bounds:
            clauses.append(f"{p}price BETWEEN ? AND ?")
            params.extend(self.price)
        if self.dates and len(self.dates) == 2 and tuple(self.dates) != tuple(self.date_bounds):
            column = "date_sold" if self.date_field == "Sale date" else "date_listed"
            clauses.append(f"{p}{column} BETWEEN ? AND ?")
            params.extend(d.isoformat() for d in self.dates)
        elif self.date_field == "Sale date":
            clauses.append(f"{p}date_sold IS NOT NULL")
        if self.status != "All":
            clauses.append(f"{p}status = ?")
            params.append(self.status)
        return ("WHERE " + " AND ".join(clauses)) if clauses else "", tuple(params)

    @property
    def active_count(self):
        return sum(bool(x) for x in [self.cities, self.property_types, self.agents, self.bedrooms,
                                     self.furnishing, self.price != self.price_bounds,
                                     self.status != "All", self.date_field == "Sale date",
                                     self.dates and tuple(self.dates) != tuple(self.date_bounds)])


def filter_options():
    return {
        "cities": q("SELECT DISTINCT city FROM listings ORDER BY 1")["city"].tolist(),
        "types": q("SELECT DISTINCT property_type FROM listings ORDER BY 1")["property_type"].tolist(),
        "agents": q("SELECT agent_id, name FROM agents ORDER BY agent_id"),
        "bedrooms": q("SELECT DISTINCT bedrooms FROM property_attributes WHERE bedrooms IS NOT NULL ORDER BY 1")["bedrooms"].tolist(),
        "furnishing": q("SELECT DISTINCT furnishing_status FROM property_attributes "
                        "WHERE furnishing_status IS NOT NULL ORDER BY 1")["furnishing_status"].tolist(),
        "price": q("SELECT MIN(price) lo, MAX(price) hi FROM listings").iloc[0],
        "listed": q("SELECT MIN(date_listed) lo, MAX(date_listed) hi FROM listings").iloc[0],
        "sold": q("SELECT MIN(date_sold) lo, MAX(date_sold) hi FROM sales").iloc[0],
    }


# ---------------------------------------------------------------- CRUD
# Column metadata for the forms: enum columns get a selectbox, flags a checkbox, dates a date picker.
ENUMS = {
    "city": config.CITIES, "property_type": config.PROPERTY_TYPES,
    "furnishing_status": config.FURNISHING, "buyer_type": config.BUYER_TYPES,
    "payment_mode": config.PAYMENT_MODES, "loan_provider": [None] + config.LOAN_PROVIDERS,
}
FLAGS = {"is_rented", "parking_available", "power_backup", "loan_taken"}
DATES = {"date_listed", "date_sold"}
# Foreign keys: column -> (parent table, parent key)
FOREIGN_KEYS = {
    "listings": {"agent_id": ("agents", "agent_id")},
    "property_attributes": {"listing_id": ("listings", "listing_id")},
    "sales": {"listing_id": ("listings", "listing_id")},
    "buyers": {"sale_id": ("sales", "sale_id")},
}
# What a delete cascades to, for the confirmation message.
CHILDREN = {
    "agents": [("listings", "agent_id", "agent_id set to NULL")],
    "listings": [("property_attributes", "listing_id", "deleted"), ("sales", "listing_id", "deleted")],
    "sales": [("buyers", "sale_id", "deleted")],
}
TABLE_LABELS = {"agents": "Agents", "listings": "Listings", "property_attributes": "Property attributes",
                "sales": "Sales", "buyers": "Buyers"}
ID_PREFIX = {"agents": ("A", 4), "listings": ("L", 5)}


def columns(table):
    return db.table_columns(table)


def primary_key(table):
    return db.primary_key(table)


def next_id(table):
    """Next free primary key: 'A0051' style for text keys, max+1 for integer keys."""
    pk = primary_key(table)
    if table in ID_PREFIX:
        prefix, width = ID_PREFIX[table]
        last = scalar(f"SELECT MAX(CAST(SUBSTR({pk}, 2) AS INTEGER)) FROM {table}") or 0
        return f"{prefix}{last + 1:0{width}d}"
    return int(scalar(f"SELECT COALESCE(MAX({pk}), 0) + 1 FROM {table}"))


def get_row(table, key):
    frame = db.query(f"SELECT * FROM {table} WHERE {primary_key(table)} = ?", (key,))
    return None if frame.empty else frame.iloc[0].to_dict()


def write(sql, params):
    """Run one write statement with foreign keys enforced. Returns (ok, message, rowcount)."""
    try:
        with db.connect() as conn:
            cur = conn.execute(sql, params)
            conn.commit()
            rowcount = cur.rowcount
    except sqlite3.IntegrityError as e:
        return False, _friendly(str(e)), 0
    except sqlite3.Error as e:
        return False, f"Database error: {e}", 0
    st.cache_data.clear()
    return True, "", rowcount


def _friendly(message):
    if "FOREIGN KEY" in message:
        return "That ID does not exist in the parent table (foreign-key check failed)."
    if "UNIQUE" in message:
        column = message.split(":")[-1].strip()
        return f"A record with that value already exists ({column} must be unique)."
    if "CHECK" in message:
        return f"A value is outside its allowed range ({message.split(':')[-1].strip()})."
    if "NOT NULL" in message:
        return f"A required field is empty ({message.split(':')[-1].strip()})."
    return message


def insert(table, values):
    cols = list(values)
    return write(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                 tuple(values[c] for c in cols))


def update(table, key, values):
    pk = primary_key(table)
    sets = ", ".join(f"{c} = ?" for c in values)
    return write(f"UPDATE {table} SET {sets} WHERE {pk} = ?", tuple(values.values()) + (key,))


def delete(table, key):
    return write(f"DELETE FROM {table} WHERE {primary_key(table)} = ?", (key,))


def delete_impact(table, key):
    """[(child table, rows, effect)] that a delete would touch, following ON DELETE rules."""
    impact = []
    for child, column, effect in CHILDREN.get(table, []):
        n = int(scalar(f"SELECT COUNT(*) FROM {child} WHERE {column} = ?", (key,)))
        if n:
            impact.append((child, n, effect))
    if table == "listings":   # buyers hang off the sale, two levels down
        n = int(scalar("SELECT COUNT(*) FROM buyers b JOIN sales s ON s.sale_id = b.sale_id "
                       "WHERE s.listing_id = ?", (key,)))
        if n:
            impact.append(("buyers", n, "deleted"))
    return impact


def restore_original():
    """Rebuild the database from the cleaned CSVs in data/processed/ (undoes every CRUD change)."""
    tables = {name: pd.read_csv(config.PROCESSED_DIR / f"{name}.csv") for name in config.TABLE_ORDER}
    db.build(tables)
    st.cache_data.clear()
