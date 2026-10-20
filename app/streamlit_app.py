"""BrickView: Real Estate Analytics Platform (Streamlit entry point).

    streamlit run app/streamlit_app.py
"""
import datetime as dt
import importlib
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
from src import db  # noqa: E402

# Streamlit Cloud only hot-reloads files under app/, so reload the root modules on every run.
importlib.reload(config)
importlib.reload(db)

import data  # noqa: E402
import ui  # noqa: E402
import views  # noqa: E402

st.set_page_config(page_title="BrickView | Real Estate Analytics", page_icon="🏙️", layout="wide",
                   initial_sidebar_state="expanded")
ui.setup_page()

if not config.DB_PATH.exists():   # first run on a fresh machine without the committed database
    with st.spinner("Building the database ..."):
        import pandas as pd

        db.build({t: pd.read_csv(config.PROCESSED_DIR / f"{t}.csv") for t in config.TABLE_ORDER})

FILTER_KEYS = ["f_city", "f_type", "f_price", "f_agent", "f_date_field", "f_dates", "f_status", "f_beds", "f_furn"]


def reset_filters():
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


def sidebar_filters(show):
    opts = data.filter_options()
    # The slider works in $ millions (two decimals) so its labels stay readable.
    lo, hi = float(opts["price"].lo // 50_000 * 0.05), float(-(-opts["price"].hi // 50_000) * 0.05)
    lo, hi = round(lo, 2), round(hi, 2)
    f = data.Filters(price=(lo * 1e6, hi * 1e6), price_bounds=(lo * 1e6, hi * 1e6))
    if not show:
        # Pages without filters still read the defaults, but keep any choices the user already made.
        return _from_state(f, opts)
    with st.sidebar:
        st.markdown("### 🎛️ Filters")
        f.cities = st.multiselect("City", opts["cities"], key="f_city", placeholder="All cities")
        f.property_types = st.multiselect("Property type", opts["types"], key="f_type", placeholder="All types")
        st.session_state.setdefault("f_price", (lo, hi))
        price = st.slider("Price range ($ millions)", lo, hi, step=0.05, key="f_price", format="$%.2fM")
        f.price = (price[0] * 1e6, price[1] * 1e6)
        agents = opts["agents"]
        f.agents = st.multiselect("Agent (type to search)", agents["agent_id"].tolist(), key="f_agent",
                                  placeholder="All agents")
        f.date_field = st.radio("Date filter on", ["Listed date", "Sale date"], horizontal=True, key="f_date_field",
                                on_change=lambda: st.session_state.pop("f_dates", None))
        rng = opts["listed"] if f.date_field == "Listed date" else opts["sold"]
        bounds = (dt.date.fromisoformat(rng.lo), dt.date.fromisoformat(rng.hi))
        f.date_bounds = bounds
        st.session_state.setdefault("f_dates", bounds)
        dates = st.date_input("Date range", min_value=bounds[0], max_value=bounds[1], key="f_dates")
        f.dates = tuple(dates) if isinstance(dates, (list, tuple)) else ()
        f.status = st.selectbox("Status", ["All", "Active", "Sold"], key="f_status")
        with st.expander("More filters"):
            f.bedrooms = st.multiselect("Bedrooms", opts["bedrooms"], key="f_beds", placeholder="Any")
            f.furnishing = st.multiselect("Furnishing", opts["furnishing"], key="f_furn", placeholder="Any")
        st.button("Reset filters", on_click=reset_filters, width="stretch")
    return f


def _from_state(f, opts):
    s = st.session_state
    f.cities, f.property_types = s.get("f_city", []), s.get("f_type", [])
    f.agents = s.get("f_agent", [])
    f.status, f.bedrooms, f.furnishing = s.get("f_status", "All"), s.get("f_beds", []), s.get("f_furn", [])
    return f


def _keep_filter_state():
    # Streamlit drops widget state for widgets not drawn in a run; re-assigning keeps it across pages.
    for key in FILTER_KEYS:
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]


_keep_filter_state()

PAGES = {
    "Dashboard": [
        st.Page(views.overview, title="Overview", icon="🏠", default=True, url_path="overview"),
        st.Page(views.explorer, title="Market Explorer", icon="🔎", url_path="explorer"),
        st.Page(views.visualizations, title="Visualizations", icon="📊", url_path="visualizations"),
        st.Page(views.agents, title="Agent Dashboard", icon="🧑‍💼", url_path="agents"),
    ],
    "SQL & data": [
        st.Page(views.sql_insights, title="SQL Insights", icon="🧮", url_path="sql-insights"),
        st.Page(views.crud, title="Data Management", icon="🛠️", url_path="data-management"),
        st.Page(views.about, title="About", icon="ℹ️", url_path="about"),
    ],
}
FILTER_PAGES = {"Market Explorer", "Visualizations", "Agent Dashboard"}

with st.sidebar:
    st.markdown("## 🏙️ BrickView")
    st.caption("Real Estate Analytics Platform")

page = st.navigation(PAGES)
st.session_state["filters"] = sidebar_filters(show=page.title in FILTER_PAGES)
with st.sidebar:
    st.divider()
    st.caption(f"[GitHub]({config.GITHUB_URL}) · built by {config.AUTHOR}")
page.run()
