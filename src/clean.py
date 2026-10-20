"""Read the five raw files, clean them and return tidy DataFrames ready for SQLite.

Every change is recorded in a cleaning log (table, step, rows affected) so the
pipeline can print and save exactly what it did.
"""
import json

import pandas as pd

import config


class CleaningLog:
    def __init__(self):
        self.rows = []

    def add(self, table, step, affected):
        self.rows.append({"table": table, "step": step, "rows_affected": int(affected)})

    def frame(self):
        return pd.DataFrame(self.rows, columns=["table", "step", "rows_affected"])


def _read(name):
    path = config.RAW_DIR / config.RAW_FILES[name]
    if path.suffix == ".csv":
        return pd.read_csv(path)
    with open(path, encoding="utf-8") as f:
        # Flatten nested JSON objects, if any, into dotted columns.
        return pd.json_normalize(json.load(f))


def _strip_strings(df):
    for col in df.select_dtypes(include="object"):
        df[col] = df[col].str.strip()
    return df


def _drop_duplicates(df, key, table, log):
    before = len(df)
    df = df.drop_duplicates(subset=key)
    log.add(table, f"drop duplicate {key}", before - len(df))
    return df


def _to_bool_int(series):
    mapping = {True: 1, False: 0, "true": 1, "false": 0, "yes": 1, "no": 0, 1: 1, 0: 0}
    lowered = series.map(lambda v: v.lower() if isinstance(v, str) else v)
    return lowered.map(mapping).fillna(0).astype(int)


def _to_date(series):
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d")


# ---------------------------------------------------------------- per-table cleaners
def clean_agents(log):
    df = _strip_strings(_read("agents"))
    df.columns = [c.lower() for c in df.columns]
    df = _drop_duplicates(df, "agent_id", "agents", log)
    for col in ["commission_rate", "rating"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").round(2)
    for col in ["deals_closed", "experience_years", "avg_closing_days"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    df["email"] = df["email"].str.lower()
    log.add("agents", "standardise column names, numeric types, lower-case emails", len(df))
    return df[["agent_id", "name", "phone", "email", "commission_rate", "deals_closed",
               "rating", "experience_years", "avg_closing_days"]]


def clean_listings(log):
    df = _strip_strings(_read("listings")).rename(columns={
        "Listing_ID": "listing_id", "City": "city", "Property_Type": "property_type",
        "Price": "price", "Sqft": "area_sqft", "Date_Listed": "date_listed",
        "Agent_ID": "agent_id", "Latitude": "latitude", "Longitude": "longitude"})
    df = _drop_duplicates(df, "listing_id", "listings", log)
    df["city"] = df["city"].str.title()
    df["property_type"] = df["property_type"].str.title()
    df["price"] = pd.to_numeric(df["price"], errors="coerce").round(2)
    df["area_sqft"] = pd.to_numeric(df["area_sqft"], errors="coerce").round(2)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce").round(6)
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce").round(6)
    df["date_listed"] = _to_date(df["date_listed"])
    log.add("listings", "round price / area to 2 dp, coordinates to 6 dp; dates to YYYY-MM-DD", len(df))
    before = len(df)
    df = df.dropna(subset=["listing_id", "city", "property_type", "price", "date_listed"])
    df = df[df["price"] > 0]
    log.add("listings", "drop rows missing id / city / type / price / date", before - len(df))
    return df[["listing_id", "city", "property_type", "price", "area_sqft", "date_listed",
               "agent_id", "latitude", "longitude"]]


def clean_attributes(log, listing_ids):
    df = _strip_strings(_read("property_attributes"))
    df.columns = [c.lower() for c in df.columns]
    df = _drop_duplicates(df, "listing_id", "property_attributes", log)
    for col in ["is_rented", "parking_available", "power_backup"]:
        df[col] = _to_bool_int(df[col])
    log.add("property_attributes", "booleans -> 0/1 integers", len(df))
    for col in ["bedrooms", "bathrooms", "floor_number", "total_floors", "year_built", "tenant_count"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    df["metro_distance_km"] = pd.to_numeric(df["metro_distance_km"], errors="coerce").round(2)

    swapped = df["floor_number"] > df["total_floors"]
    df.loc[swapped, ["floor_number", "total_floors"]] = df.loc[swapped, ["total_floors", "floor_number"]].values
    log.add("property_attributes", "swap floor_number / total_floors where floor > total floors", swapped.sum())

    orphan = ~df["listing_id"].isin(listing_ids)
    df = df[~orphan]
    log.add("property_attributes", "drop rows whose listing_id is not in listings", orphan.sum())
    return df[["attribute_id", "listing_id", "bedrooms", "bathrooms", "floor_number", "total_floors",
               "year_built", "is_rented", "tenant_count", "furnishing_status", "metro_distance_km",
               "parking_available", "power_backup"]]


def clean_sales(log, listings):
    df = _strip_strings(_read("sales")).rename(columns={
        "Listing_ID": "listing_id", "Sale_Price": "sale_price",
        "Date_Sold": "date_sold", "Days_on_Market": "days_on_market"})
    df = _drop_duplicates(df, "listing_id", "sales", log)
    orphan = ~df["listing_id"].isin(listings["listing_id"])
    df = df[~orphan]
    log.add("sales", "drop rows whose listing_id is not in listings", orphan.sum())

    df["sale_price"] = pd.to_numeric(df["sale_price"], errors="coerce").round(2)
    df["date_sold"] = _to_date(df["date_sold"])
    # days_on_market arrives as a float with tiny noise (e.g. 65.0056); it equals the gap between
    # the listing and sale dates, so store the exact whole-day gap.
    listed = df["listing_id"].map(listings.set_index("listing_id")["date_listed"])
    gap = (pd.to_datetime(df["date_sold"]) - pd.to_datetime(listed)).dt.days
    raw = pd.to_numeric(df["days_on_market"], errors="coerce")
    log.add("sales", "days_on_market: noisy float -> whole days from the two dates "
                     f"(max difference {(raw - gap).abs().max():.3f} days)", len(df))
    df["days_on_market"] = gap.astype("Int64")

    df = df.sort_values("listing_id").reset_index(drop=True)
    df.insert(0, "sale_id", range(1, len(df) + 1))
    log.add("sales", "add surrogate key sale_id (1..n, ordered by listing_id)", len(df))
    return df[["sale_id", "listing_id", "sale_price", "date_sold", "days_on_market"]]


def clean_buyers(log, sales):
    df = _strip_strings(_read("buyers"))
    df.columns = [c.lower() for c in df.columns]
    df = _drop_duplicates(df, "buyer_id", "buyers", log)
    # The raw "sale_id" column holds listing IDs (e.g. "L01179"). Resolve it to the real sale_id.
    sale_of_listing = sales.set_index("listing_id")["sale_id"]
    df["sale_id"] = df["sale_id"].map(sale_of_listing)
    unmatched = df["sale_id"].isna()
    df = df[~unmatched]
    log.add("buyers", "map raw sale_id (a listing id) -> sales.sale_id; drop unmatched", unmatched.sum())
    df["sale_id"] = df["sale_id"].astype(int)

    df["loan_taken"] = _to_bool_int(df["loan_taken"])
    df["loan_amount"] = pd.to_numeric(df["loan_amount"], errors="coerce").fillna(0).round(2)
    no_loan = df["loan_taken"] == 0
    df.loc[no_loan, "loan_provider"] = None
    log.add("buyers", "loan_taken -> 0/1; provider NULL and amount 0 when no loan", no_loan.sum())
    return df[["buyer_id", "sale_id", "buyer_type", "payment_mode", "loan_taken",
               "loan_provider", "loan_amount"]]


def clean_all():
    """Return ({table: DataFrame}, cleaning-log DataFrame)."""
    log = CleaningLog()
    agents = clean_agents(log)
    listings = clean_listings(log)
    unknown_agent = ~listings["agent_id"].isin(agents["agent_id"])
    listings.loc[unknown_agent, "agent_id"] = None
    log.add("listings", "set agent_id NULL where the agent does not exist", unknown_agent.sum())
    attributes = clean_attributes(log, set(listings["listing_id"]))
    sales = clean_sales(log, listings)
    buyers = clean_buyers(log, sales)
    tables = {"agents": agents, "listings": listings, "property_attributes": attributes,
              "sales": sales, "buyers": buyers}
    return tables, log.frame()
