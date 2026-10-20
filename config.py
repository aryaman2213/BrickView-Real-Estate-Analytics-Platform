"""Paths, cleaning rules and dashboard settings for BrickView, in one place."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------- paths
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DB_PATH = ROOT / "db" / "brickview.db"
SCHEMA_PATH = ROOT / "sql" / "schema.sql"
QUERIES_PATH = ROOT / "sql" / "queries.sql"

RAW_FILES = {
    "listings": "listings_final_expanded.json",
    "property_attributes": "property_attributes_final_expanded.json",
    "agents": "agents_cleaned.json",
    "sales": "sales_cleaned.csv",
    "buyers": "buyers_cleaned.json",
}

# Load order respects foreign keys (parents before children).
TABLE_ORDER = ["agents", "listings", "property_attributes", "sales", "buyers"]

# ---------------------------------------------------------------- domain values
CITIES = ["Chicago", "Houston", "Los Angeles", "New York", "Phoenix"]
PROPERTY_TYPES = ["Apartment", "Condo", "House", "Townhouse"]
FURNISHING = ["Furnished", "Semi-Furnished", "Unfurnished"]
BUYER_TYPES = ["End User", "Investor"]
PAYMENT_MODES = ["Bank Transfer", "Cash", "Cheque", "UPI"]
LOAN_PROVIDERS = ["Axis", "HDFC", "ICICI", "PNB", "SBI"]

# Real city centres, used only for the city-summary map (the listing coordinates in the
# dataset are random points across the US and do not match their city; see README).
CITY_CENTRES = {
    "Chicago": (41.8781, -87.6298),
    "Houston": (29.7604, -95.3698),
    "Los Angeles": (34.0522, -118.2437),
    "New York": (40.7128, -74.0060),
    "Phoenix": (33.4484, -112.0740),
}

# ---------------------------------------------------------------- analysis bands
# Price buckets (USD). Listing prices run from $100k to $5M.
PRICE_BUCKETS = [(0, 1_000_000, "Under $1M"), (1_000_000, 2_000_000, "$1M-2M"),
                 (2_000_000, 3_000_000, "$2M-3M"), (3_000_000, 4_000_000, "$3M-4M"),
                 (4_000_000, float("inf"), "$4M+")]
SLOW_SALE_DAYS = 90

# ---------------------------------------------------------------- app
CURRENCY = "$"
GITHUB_URL = "https://github.com/aryaman2213/BrickView-Real-Estate-Analytics-Platform"
LIVE_URL = "https://brickview-real-estate.streamlit.app"
AUTHOR = "Aryaman Bhatnagar"
AUTHOR_EMAIL = "aryamanbhatnagar2273@gmail.com"
