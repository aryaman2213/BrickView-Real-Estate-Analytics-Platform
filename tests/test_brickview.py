"""Checks for the pipeline output, the schema, the 30 business queries, the filters and CRUD.

    pytest -q
"""
import shutil
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

import config  # noqa: E402
from src import db  # noqa: E402

EXPECTED_ROWS = {"agents": 50, "listings": 21_200, "property_attributes": 21_200, "sales": 720, "buyers": 20_000}


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """A throw-away copy of the database; config.DB_PATH points at it for the test."""
    path = tmp_path / "brickview.db"
    shutil.copy(config.DB_PATH, path)
    monkeypatch.setattr(config, "DB_PATH", path)
    return path


# ---------------------------------------------------------------- data + schema
def test_row_counts():
    for table, n in EXPECTED_ROWS.items():
        assert db.query(f"SELECT COUNT(*) n FROM {table}")["n"][0] == n


def test_integrity_and_foreign_keys():
    assert db.integrity_report() == {"foreign_key_violations": 0, "integrity_check": "ok"}


def test_schema_objects():
    objects = db.query("SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")
    assert set(objects.query("type == 'table'")["name"]) == set(EXPECTED_ROWS)
    assert len(objects.query("type == 'index'")) >= 10
    assert {"v_listing_details", "v_active_listings", "v_sale_details", "v_buyer_details",
            "v_agent_performance", "v_city_summary"} <= set(objects.query("type == 'view'")["name"])


def test_processed_csvs_match_database():
    for table, n in EXPECTED_ROWS.items():
        assert len(pd.read_csv(config.PROCESSED_DIR / f"{table}.csv")) == n


def test_cleaning_rules():
    assert db.query("SELECT COUNT(*) n FROM property_attributes WHERE floor_number > total_floors")["n"][0] == 0
    gap = db.query("""SELECT MAX(ABS(julianday(s.date_sold) - julianday(l.date_listed) - s.days_on_market)) d
                      FROM sales s JOIN listings l USING (listing_id)""")["d"][0]
    assert gap == 0
    assert db.query("SELECT COUNT(*) n FROM buyers WHERE loan_taken = 0 AND loan_provider IS NOT NULL")["n"][0] == 0


# ---------------------------------------------------------------- business queries
QUERIES = db.load_queries()


def test_thirty_queries_with_metadata():
    assert [q["id"] for q in QUERIES] == [f"Q{i:02d}" for i in range(1, 31)]
    assert all(q["question"].endswith("?") and q["insight"] and q["sql"] for q in QUERIES)


@pytest.mark.parametrize("item", QUERIES, ids=[q["id"] for q in QUERIES])
def test_query_runs_and_returns_rows(item):
    result = db.query(item["sql"])
    assert not result.empty
    kind, opts = db.parse_chart(item["chart"])
    for axis in ("x", "y", "names", "values", "color"):
        if axis in opts:
            assert opts[axis] in result.columns, f"{item['id']} chart column {opts[axis]} missing"


def _q(qid):
    return db.query(next(q["sql"] for q in QUERIES if q["id"] == qid))


def test_query_answers_match_pandas():
    listings = pd.read_csv(config.PROCESSED_DIR / "listings.csv")
    sales = pd.read_csv(config.PROCESSED_DIR / "sales.csv")
    q01 = _q("Q01").set_index("city")["avg_list_price"]
    assert (q01 - listings.groupby("city")["price"].mean().round(2)).abs().max() < 0.01
    merged = sales.merge(listings, on="listing_id")
    above = (merged["sale_price"] > merged["price"]).mean() * 100
    assert _q("Q13").set_index("outcome").loc["Above list price", "pct_of_sales"] == pytest.approx(above, abs=0.01)
    assert len(_q("Q15")) == (sales["days_on_market"] > 90).sum()
    assert len(_q("Q18")) == len(listings) - len(sales)
    median = listings.groupby("city")["price"].median()
    q09 = _q("Q09").set_index("city")["median_list_price"]
    assert (q09 - median).abs().max() < 0.01


# ---------------------------------------------------------------- filters + read-only SQL
def test_filter_where_clause():
    import data

    f = data.Filters(cities=["New York"], property_types=["Condo"], price=(1e6, 2e6), price_bounds=(1e5, 5e6),
                     status="Sold")
    where, params = f.where()
    n = db.query(f"SELECT COUNT(*) n FROM v_listing_details {where}", params)["n"][0]
    expected = db.query("""SELECT COUNT(*) n FROM listings l JOIN sales s USING (listing_id)
                           WHERE city = 'New York' AND property_type = 'Condo'
                             AND price BETWEEN 1000000 AND 2000000""")["n"][0]
    assert n == expected > 0
    assert data.Filters().where() == ("", ())


def test_readonly_sql_blocks_writes():
    import data

    assert len(data.run_readonly("SELECT * FROM agents")) == 50
    for bad in ["DELETE FROM agents", "SELECT 1; DROP TABLE agents", "UPDATE agents SET name = 'x'"]:
        with pytest.raises((ValueError, sqlite3.Error)):
            data.run_readonly(bad)


# ---------------------------------------------------------------- CRUD
def test_crud_round_trip(temp_db):
    import data

    new_id = data.next_id("agents")
    assert new_id == "A0051"
    ok, msg, _ = data.insert("agents", {"agent_id": new_id, "name": "Test Agent", "email": "t@x.com",
                                         "commission_rate": 2.5, "rating": 4.2})
    assert ok, msg
    ok, _, n = data.update("agents", new_id, {"rating": 4.8})
    assert ok and n == 1 and data.get_row("agents", new_id)["rating"] == 4.8
    ok, _, n = data.delete("agents", new_id)
    assert ok and n == 1 and data.get_row("agents", new_id) is None


def test_constraints_are_enforced(temp_db):
    import data

    ok, msg, _ = data.insert("listings", {"listing_id": "L99999", "city": "Chicago", "property_type": "Condo",
                                           "price": 500000, "date_listed": "2024-01-01", "agent_id": "A9999"})
    assert not ok and "foreign-key" in msg
    ok, msg, _ = data.update("agents", "A0001", {"rating": 7})
    assert not ok and "range" in msg
    sold = db.query("SELECT listing_id FROM sales LIMIT 1")["listing_id"][0]
    ok, msg, _ = data.insert("sales", {"sale_id": 9999, "listing_id": sold, "sale_price": 1, "date_sold": "2024-01-01"})
    assert not ok and "unique" in msg   # a listing can only be sold once


def test_delete_cascades(temp_db):
    import data

    listing = db.query("SELECT listing_id FROM sales s WHERE EXISTS "
                       "(SELECT 1 FROM buyers b WHERE b.sale_id = s.sale_id) LIMIT 1")["listing_id"][0]
    impact = dict((t, n) for t, n, _ in data.delete_impact("listings", listing))
    assert impact["property_attributes"] == 1 and impact["sales"] == 1 and impact["buyers"] > 0
    before = db.query("SELECT COUNT(*) n FROM buyers")["n"][0]
    assert data.delete("listings", listing)[0]
    assert db.query("SELECT COUNT(*) n FROM buyers")["n"][0] == before - impact["buyers"]
    assert db.integrity_report()["foreign_key_violations"] == 0


def test_restore_original(temp_db):
    import data

    data.delete("agents", "A0001")
    data.restore_original()
    assert db.query("SELECT COUNT(*) n FROM agents")["n"][0] == 50
    assert db.query("SELECT COUNT(*) n FROM listings WHERE agent_id IS NULL")["n"][0] == 0
