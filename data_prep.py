import json
import pandas as pd
import os

# ─── Paths ───────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def load_json(filename):
    with open(os.path.join(DATA_DIR, filename), "r") as f:
        return json.load(f)

def load_csv(filename):
    return pd.read_csv(os.path.join(DATA_DIR, filename))


# ─── 1. Listings ─────────────────────────────────────────────────────────────
def prep_listings():
    data = load_json("listings_final_expanded.json")
    df = pd.DataFrame(data)

    # Standardize column names
    df.columns = [c.strip() for c in df.columns]

    # Rename to consistent names
    df.rename(columns={
        "Listing_ID": "listing_id",
        "City": "city",
        "Property_Type": "property_type",
        "Price": "price",
        "Sqft": "area_sqft",
        "Date_Listed": "date_listed",
        "Agent_ID": "agent_id",
        "Latitude": "latitude",
        "Longitude": "longitude"
    }, inplace=True)

    # Clean price and area
    df["price"] = pd.to_numeric(df["price"], errors="coerce").round(2)
    df["area_sqft"] = pd.to_numeric(df["area_sqft"], errors="coerce").round(2)

    # Standardize date
    df["date_listed"] = pd.to_datetime(df["date_listed"], errors="coerce").dt.strftime("%Y-%m-%d")

    # Drop duplicates
    df.drop_duplicates(subset="listing_id", inplace=True)
    df.dropna(subset=["listing_id", "city", "price"], inplace=True)

    print(f"✅ Listings: {len(df)} records")
    return df


# ─── 2. Property Attributes ───────────────────────────────────────────────────
def prep_attributes():
    data = load_json("property_attributes_final_expanded.json")
    df = pd.DataFrame(data)

    df.rename(columns={
        "attribute_id": "attribute_id",
        "listing_id": "listing_id",
        "bedrooms": "bedrooms",
        "bathrooms": "bathrooms",
        "floor_number": "floor_number",
        "total_floors": "total_floors",
        "year_built": "year_built",
        "is_rented": "is_rented",
        "tenant_count": "tenant_count",
        "furnishing_status": "furnishing_status",
        "metro_distance_km": "metro_distance_km",
        "parking_available": "parking_available",
        "power_backup": "power_backup"
    }, inplace=True)

    # Convert booleans to integers (SQLite doesn't have bool)
    df["is_rented"] = df["is_rented"].astype(bool).astype(int)
    df["parking_available"] = df["parking_available"].astype(bool).astype(int)
    df["power_backup"] = df["power_backup"].astype(bool).astype(int)

    # Clean numerics
    df["bedrooms"] = pd.to_numeric(df["bedrooms"], errors="coerce").fillna(0).astype(int)
    df["bathrooms"] = pd.to_numeric(df["bathrooms"], errors="coerce").fillna(0).astype(int)
    df["year_built"] = pd.to_numeric(df["year_built"], errors="coerce").fillna(0).astype(int)
    df["metro_distance_km"] = pd.to_numeric(df["metro_distance_km"], errors="coerce").round(2)

    df.drop_duplicates(subset="listing_id", inplace=True)
    df.dropna(subset=["listing_id"], inplace=True)

    print(f"✅ Attributes: {len(df)} records")
    return df


# ─── 3. Agents ────────────────────────────────────────────────────────────────
def prep_agents():
    data = load_json("agents_cleaned.json")
    df = pd.DataFrame(data)

    df.rename(columns={
        "Agent_ID": "agent_id",
        "Name": "name",
        "Phone": "phone",
        "Email": "email",
        "commission_rate": "commission_rate",
        "deals_closed": "deals_closed",
        "rating": "rating",
        "experience_years": "experience_years",
        "avg_closing_days": "avg_closing_days"
    }, inplace=True)

    df["commission_rate"] = pd.to_numeric(df["commission_rate"], errors="coerce").round(2)
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").round(1)
    df["deals_closed"] = pd.to_numeric(df["deals_closed"], errors="coerce").fillna(0).astype(int)
    df["experience_years"] = pd.to_numeric(df["experience_years"], errors="coerce").fillna(0).astype(int)
    df["avg_closing_days"] = pd.to_numeric(df["avg_closing_days"], errors="coerce").round(1)

    df.drop_duplicates(subset="agent_id", inplace=True)
    df.dropna(subset=["agent_id"], inplace=True)

    print(f"✅ Agents: {len(df)} records")
    return df


# ─── 4. Sales ─────────────────────────────────────────────────────────────────
def prep_sales():
    df = load_csv("sales_cleaned.csv")

    df.rename(columns={
        "Listing_ID": "listing_id",
        "Sale_Price": "sale_price",
        "Date_Sold": "date_sold",
        "Days_on_Market": "days_on_market"
    }, inplace=True)

    # Generate Sale_ID
    df.insert(0, "sale_id", ["S" + str(i+1).zfill(5) for i in range(len(df))])

    df["sale_price"] = pd.to_numeric(df["sale_price"], errors="coerce").round(2)
    df["days_on_market"] = pd.to_numeric(df["days_on_market"], errors="coerce").round(1)
    df["date_sold"] = pd.to_datetime(df["date_sold"], errors="coerce").dt.strftime("%Y-%m-%d")

    df.drop_duplicates(subset="listing_id", inplace=True)
    df.dropna(subset=["listing_id", "sale_price"], inplace=True)

    print(f"✅ Sales: {len(df)} records")
    return df


# ─── 5. Buyers ────────────────────────────────────────────────────────────────
def prep_buyers():
    data = load_json("buyers_cleaned.json")
    df = pd.DataFrame(data)

    df.rename(columns={
        "buyer_id": "buyer_id",
        "sale_id": "listing_id",   # sale_id in buyers actually stores listing_id
        "buyer_type": "buyer_type",
        "payment_mode": "payment_mode",
        "loan_taken": "loan_taken",
        "loan_provider": "loan_provider",
        "loan_amount": "loan_amount"
    }, inplace=True)

    df["loan_taken"] = df["loan_taken"].astype(bool).astype(int)
    df["loan_amount"] = pd.to_numeric(df["loan_amount"], errors="coerce").fillna(0).round(2)
    df["loan_provider"] = df["loan_provider"].fillna("None")

    df.drop_duplicates(subset="buyer_id", inplace=True)
    df.dropna(subset=["buyer_id"], inplace=True)

    print(f"✅ Buyers: {len(df)} records")
    return df


# ─── Run All ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🔄 Starting data preparation...\n")
    df_listings = prep_listings()
    df_attributes = prep_attributes()
    df_agents = prep_agents()
    df_sales = prep_sales()
    df_buyers = prep_buyers()
    print("\n✅ All datasets prepared successfully!")
