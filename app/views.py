"""One function per dashboard page."""
import datetime as dt

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
import data
import ui
from data import q, scalar


def _filters():
    return st.session_state["filters"]


def _filtered_listings(columns="*"):
    where, params = _filters().where()
    return q(f"SELECT {columns} FROM v_listing_details {where}", params)


def _filter_banner():
    f = _filters()
    if f.active_count:
        st.caption(f"🔎 {f.active_count} sidebar filter(s) active: every number and chart on this page uses them.")


# ================================================================ Overview
def overview():
    ui.hero("BrickView: Real Estate Analytics",
            "Listings, sales, agents and buyers from five US cities, cleaned into a normalised SQLite "
            "database and explored through SQL-driven dashboards.")
    k = q("""SELECT (SELECT COUNT(*) FROM listings) listings,
                    (SELECT COUNT(*) FROM v_active_listings) active,
                    (SELECT COUNT(*) FROM sales) sales,
                    (SELECT AVG(price) FROM listings) avg_price,
                    (SELECT SUM(sale_price) FROM sales) revenue,
                    (SELECT AVG(days_on_market) FROM sales) dom,
                    (SELECT AVG(sale_to_list_ratio) FROM v_sale_details) ratio,
                    (SELECT COUNT(*) FROM agents) agents,
                    (SELECT COUNT(*) FROM buyers) buyers""").iloc[0]
    c = st.columns(4)
    c[0].metric("Total listings", ui.number(k.listings))
    c[1].metric("Active (unsold)", f"{ui.number(k.active)} ({k.active / k.listings:.1%})")
    c[2].metric("Properties sold", ui.number(k.sales))
    c[3].metric("Sales revenue", ui.money(k.revenue))
    c = st.columns(4)
    c[0].metric("Average list price", ui.money(k.avg_price))
    c[1].metric("Average days on market", ui.number(k.dom, 1))
    c[2].metric("Average sale-to-list ratio", f"{k.ratio:.4f}")
    c[3].metric("Agents · buyer records", f"{int(k.agents)} · {int(k.buyers):,}")

    st.subheader("Key findings")
    left, right = st.columns([3, 2])
    with left:
        ui.md("""
1. **Prices are close to fair value.** 49% of homes sold above list and 51% below; sale-to-list stays
   within 0.2% of 1.00 in every city.
2. **New York is the priciest market** ($2.49M average list price), but the five cities are only 2.6% apart.
3. **Houses sell fastest** (58 days on market on average); **condos are slowest** (67 days).
   Houston turns over fastest of the cities (58.5 days), Los Angeles slowest (65.1).
4. **Location and amenities barely move prices.** No metro premium (homes 10 km+ out list *higher*), and
   parking + power backup adds only about 4% to the sale price.
5. **Sales peaked in October 2023** (64 sales) and slowed through 2024. 26% of sales took more than 90 days.
6. **Agent ratings don't predict speed.** Top-rated agents (4.5+) close no faster than 4.0-4.4 agents.
7. **Buyers split 50/50** between investors and end users, half use a loan, and payment modes are evenly used.
""")
    with right:
        city = q("SELECT city, listings, sales, avg_list_price FROM v_city_summary ORDER BY avg_list_price DESC")
        fig = px.bar(city, x="city", y="avg_list_price", text=city["avg_list_price"].map(ui.money),
                     title="Average list price by city", color="city", color_discrete_map=ui.CITY_COLORS)
        fig.update_traces(textposition="outside", textangle=0)
        fig.update_layout(showlegend=False, yaxis_title=None, xaxis_title=None)
        fig.update_yaxes(range=[2_300_000, 2_530_000])
        ui.chart(fig, 330)

    st.subheader("What's inside")
    cards = [("🔎 Market Explorer", "Filter by city, type, price, agent, dates, bedrooms and status; paged, sortable, downloadable."),
             ("📊 Visualizations", "Listings map, price and type breakdowns, monthly sales vs listings, buyers and financing."),
             ("🧑‍💼 Agent Dashboard", "Leaderboard, a profile for any agent, and experience / rating vs performance."),
             ("🧮 SQL Insights", "All 30 business questions: the SQL, its live output, a chart and the finding."),
             ("🛠️ Data Management", "Create, read, update and delete records in all five tables, with constraint checks.")]
    cols = st.columns(len(cards))
    for col, (title, text) in zip(cols, cards):
        with col.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(text)
    ui.note("The dataset is synthetic coursework data. Read the data notes on the <b>About</b> page before "
            "drawing conclusions (for example, listing coordinates do not match their city).")


# ================================================================ Explorer (filters page)
EXPLORER_COLUMNS = ["listing_id", "city", "property_type", "price", "area_sqft", "price_per_sqft",
                    "bedrooms", "bathrooms", "furnishing_status", "metro_distance_km", "year_built",
                    "date_listed", "agent_id", "agent_name", "status", "sale_price", "date_sold",
                    "days_on_market"]


def explorer():
    ui.header("🔎 Market Explorer",
              "Set filters in the sidebar (city, property type, price, agent, listed / sale date, bedrooms, "
              "furnishing, status). Results update instantly.")
    f = _filters()
    where, params = f.where()
    k = q(f"""SELECT COUNT(*) n, AVG(price) avg_price, AVG(price_per_sqft) ppsf,
                     SUM(status = 'Sold') sold, AVG(days_on_market) dom
              FROM v_listing_details {where}""", params).iloc[0]
    c = st.columns(5)
    c[0].metric("Matching listings", ui.number(k.n))
    c[1].metric("Average price", ui.money(k.avg_price))
    c[2].metric("Avg price / sq ft", ui.money(k.ppsf, short=False))
    c[3].metric("Sold", ui.number(k.sold or 0))
    c[4].metric("Avg days on market", ui.number(k.dom, 1))
    if not k.n:
        st.warning("No listings match these filters. Widen them in the sidebar.")
        return

    search = st.text_input("Search listing ID or agent", placeholder="e.g. L00042 or A0011",
                           key="explorer_search").strip()
    frame = q(f"SELECT {', '.join(EXPLORER_COLUMNS)} FROM v_listing_details {where} "
              f"ORDER BY listing_id", params)
    if search:
        mask = (frame["listing_id"].str.contains(search, case=False)
                | frame["agent_id"].fillna("").str.contains(search, case=False)
                | frame["agent_name"].fillna("").str.contains(search, case=False))
        frame = frame[mask]
    ui.paged_table(frame, key="explorer")
    st.download_button("⬇️ Download filtered listings (CSV)", frame.to_csv(index=False).encode(),
                       "brickview_listings.csv", "text/csv")


# ================================================================ Visualizations
def visualizations():
    ui.header("📊 Visualizations", "Market, sales and buyer views. The sidebar filters apply to every chart.")
    _filter_banner()
    tabs = st.tabs(["🗺️ Map", "🏙️ Market", "📈 Sales trend", "💳 Buyers & financing"])
    with tabs[0]:
        _map()
    with tabs[1]:
        _market()
    with tabs[2]:
        _sales()
    with tabs[3]:
        _buyers()


def _map():
    mode = st.radio("Map view", ["Listings (points)", "City summary (bubbles)"], horizontal=True,
                    key="map_mode")
    f = _filters()
    where, params = f.where()
    if mode.startswith("Listings"):
        status_default = f.status
        show = st.segmented_control("Show", ["Active", "Sold", "All"], default=status_default, key="map_status")
        extra = "" if show in (None, "All") else (" AND " if where else "WHERE ") + "status = ?"
        extra_params = () if show in (None, "All") else (show,)
        total = scalar(f"SELECT COUNT(*) FROM v_listing_details {where}{extra}", params + extra_params)
        limit = 6000
        pts = q(f"""SELECT listing_id, city, property_type, price, status, latitude, longitude
                    FROM v_listing_details {where}{extra}
                    ORDER BY listing_id LIMIT {limit}""", params + extra_params)
        if pts.empty:
            st.info("No listings to plot for these filters.")
            return
        pts = pts.sort_values("property_type")
        pts["price_label"] = pts["price"].map(ui.money)
        fig = px.scatter_map(pts, lat="latitude", lon="longitude", color="property_type",
                             color_discrete_map=ui.TYPE_COLORS, zoom=2.9, center=dict(lat=37.5, lon=-96),
                             hover_name="listing_id",
                             hover_data={"city": True, "property_type": True, "price_label": True,
                                         "status": True, "latitude": ":.4f", "longitude": ":.4f"},
                             labels={"price_label": "price", "property_type": "Property type"},
                             map_style="carto-positron")
        fig.update_traces(marker=dict(size=6, opacity=0.75))
        fig.update_layout(legend=dict(orientation="h", y=1.02, x=0))
        ui.chart(fig, 560)
        st.caption(f"Showing {len(pts):,} of {total:,} {'' if show in (None, 'All') else show.lower() + ' '}"
                   f"listings{' (first ' + format(limit, ',') + ' by ID)' if total > limit else ''}. "
                   "Hover a point for its details.")
        ui.note("Listing coordinates in the source data are random points across the US and don't match "
                "their city (a 'New York' listing can sit in Texas). Use <b>City summary</b> for a "
                "geographically correct view.")
    else:
        city = q(f"""SELECT city, COUNT(*) listings, SUM(status = 'Active') active,
                            SUM(status = 'Sold') sold, AVG(price) avg_price
                     FROM v_listing_details {where} GROUP BY city""", params)
        if city.empty:
            st.info("No listings for these filters.")
            return
        city["lat"] = city["city"].map(lambda c: config.CITY_CENTRES[c][0])
        city["lon"] = city["city"].map(lambda c: config.CITY_CENTRES[c][1])
        city["avg_price_label"] = city["avg_price"].map(ui.money)
        fig = px.scatter_map(city, lat="lat", lon="lon", size="listings", color="city",
                             color_discrete_map=ui.CITY_COLORS, size_max=60, zoom=3,
                             center=dict(lat=37.5, lon=-96), hover_name="city",
                             hover_data={"listings": ":,", "active": ":,", "sold": ":,",
                                         "avg_price_label": True, "lat": False, "lon": False},
                             labels={"avg_price_label": "avg price"}, map_style="carto-positron")
        ui.chart(fig, 560)
        st.caption("Bubbles sit at each city's real centre; bubble size = number of listings.")


def _market():
    df = _filtered_listings("city, property_type, price, area_sqft, price_per_sqft, furnishing_status, status")
    if df.empty:
        st.info("No listings for these filters.")
        return
    metric = st.radio("Bar chart shows", ["Number of listings", "Average price"], horizontal=True,
                      key="market_metric")
    c1, c2 = st.columns(2)
    with c1:
        if metric == "Number of listings":
            by_city = df.groupby("city").size().reset_index(name="listings").sort_values("listings", ascending=False)
            fig = px.bar(by_city, x="city", y="listings", color="city", title="Listings by city",
                         color_discrete_map=ui.CITY_COLORS, text_auto=",")
        else:
            by_city = df.groupby("city")["price"].mean().reset_index(name="avg_price").sort_values("avg_price", ascending=False)
            fig = px.bar(by_city, x="city", y="avg_price", color="city", title="Average list price by city",
                         color_discrete_map=ui.CITY_COLORS, text=by_city["avg_price"].map(ui.money))
            lo, hi = by_city["avg_price"].min(), by_city["avg_price"].max()
            fig.update_yaxes(range=[lo * 0.95, hi * 1.02])
        fig.update_layout(showlegend=False, xaxis_title=None)
        ui.chart(fig)
    with c2:
        types = df.groupby("property_type").size().reset_index(name="listings")
        fig = px.pie(types, names="property_type", values="listings", hole=0.5, title="Property type mix",
                     color="property_type", color_discrete_map=ui.TYPE_COLORS)
        fig.update_traces(textinfo="percent+label")
        ui.chart(fig)
    c3, c4 = st.columns(2)
    with c3:
        fig = px.histogram(df, x="price", nbins=40, title="Price distribution", color_discrete_sequence=[ui.BRICK])
        fig.update_layout(bargap=0.05, yaxis_title="listings")
        ui.chart(fig)
    with c4:
        ppsf = df.groupby(["property_type", "furnishing_status"])["price_per_sqft"].median().reset_index()
        fig = px.bar(ppsf, x="property_type", y="price_per_sqft", color="furnishing_status", barmode="group",
                     title="Median price per sq ft by type and furnishing",
                     color_discrete_sequence=ui.PALETTE[1:])
        fig.update_layout(xaxis_title=None, legend_title=None)
        ui.chart(fig)


def _sales():
    f = _filters()
    where, params = f.where()
    listed = q(f"SELECT strftime('%Y-%m', date_listed) month, COUNT(*) n FROM v_listing_details {where} "
               "GROUP BY month", params)
    sold = q(f"""SELECT strftime('%Y-%m', date_sold) month, COUNT(*) n, SUM(sale_price) revenue
                 FROM v_listing_details {where}{' AND ' if where else 'WHERE '}date_sold IS NOT NULL
                 GROUP BY month""", params)
    if listed.empty:
        st.info("No listings for these filters.")
        return
    trend = listed.rename(columns={"n": "New listings"}).merge(
        sold.rename(columns={"n": "Sales"}), on="month", how="outer").sort_values("month")
    trend["New listings"] = trend["New listings"].fillna(0)   # Sales stays empty where none were recorded
    fig = go.Figure()
    fig.add_bar(x=trend["month"], y=trend["New listings"], name="New listings", marker_color="#d6c3b8")
    fig.add_scatter(x=trend["month"], y=trend["Sales"], name="Sales", yaxis="y2", mode="lines+markers",
                    line=dict(color=ui.BRICK, width=3))
    fig.update_layout(title="Monthly new listings (bars, left axis) and sales (line, right axis)",
                      yaxis=dict(title="new listings"),
                      yaxis2=dict(title="sales", overlaying="y", side="right", showgrid=False),
                      legend=dict(orientation="h", y=-0.12, x=0))
    ui.chart(fig, 440)
    st.caption("Sales only exist for 2023-01 to 2024-09; listings run to 2024-12.")

    sales = q(f"""SELECT property_type, city, days_on_market, sale_price, price,
                         sale_price / price AS ratio
                  FROM v_listing_details {where}{' AND ' if where else 'WHERE '}status = 'Sold'""", params)
    if sales.empty:
        st.info("None of the filtered listings has been sold.")
        return
    c1, c2 = st.columns(2)
    with c1:
        dom = sales.groupby("property_type")["days_on_market"].mean().reset_index().sort_values("days_on_market")
        fig = px.bar(dom, x="days_on_market", y="property_type", orientation="h", title="Average days on market by type",
                     text=dom["days_on_market"].round(1), color="property_type", color_discrete_map=ui.TYPE_COLORS)
        fig.update_layout(showlegend=False, yaxis_title=None)
        ui.chart(fig, 330)
    with c2:
        fig = px.histogram(sales, x="ratio", nbins=30, title="Sale-to-list price ratio",
                           color_discrete_sequence=[ui.BRICK])
        fig.add_vline(x=1, line_dash="dash", line_color=ui.INK)
        fig.update_layout(bargap=0.05, xaxis_title="sale price ÷ list price", yaxis_title="sales")
        ui.chart(fig, 330)


def _buyers():
    f = _filters()
    where, params = f.where("v")
    buyers = q(f"""SELECT b.buyer_type, b.payment_mode, b.loan_taken, b.loan_provider, b.loan_amount, v.city
                   FROM buyers b JOIN v_listing_details v ON v.sale_id = b.sale_id {where}""", params)
    if buyers.empty:
        st.info("No buyer records for these filters (buyers exist only for sold listings).")
        return
    c = st.columns(4)
    c[0].metric("Buyer records", ui.number(len(buyers)))
    c[1].metric("Investors", ui.pct(100 * (buyers["buyer_type"] == "Investor").mean()))
    c[2].metric("Loan uptake", ui.pct(100 * buyers["loan_taken"].mean()))
    c[3].metric("Average loan", ui.money(buyers.loc[buyers["loan_taken"] == 1, "loan_amount"].mean()))
    c1, c2 = st.columns(2)
    with c1:
        bt = buyers["buyer_type"].value_counts().reset_index()
        fig = px.pie(bt, names="buyer_type", values="count", hole=0.5, title="Investors vs end users",
                     color_discrete_sequence=[ui.BRICK, "#2563eb"])
        ui.chart(fig, 330)
    with c2:
        pm = buyers["payment_mode"].value_counts().reset_index()
        fig = px.bar(pm, x="payment_mode", y="count", title="Payment mode", text_auto=",",
                     color_discrete_sequence=[ui.BRICK])
        fig.update_layout(xaxis_title=None, yaxis_title="buyers")
        ui.chart(fig, 330)
    c3, c4 = st.columns(2)
    with c3:
        up = buyers.groupby("city")["loan_taken"].mean().mul(100).reset_index().sort_values("loan_taken", ascending=False)
        fig = px.bar(up, x="city", y="loan_taken", title="Loan uptake by city (%)",
                     text=up["loan_taken"].round(1), color="city", color_discrete_map=ui.CITY_COLORS)
        fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title="% of buyers with a loan")
        ui.chart(fig, 330)
    with c4:
        lp = buyers.loc[buyers["loan_taken"] == 1, "loan_provider"].value_counts().reset_index()
        fig = px.bar(lp, x="loan_provider", y="count", title="Loans by provider", text_auto=",",
                     color_discrete_sequence=["#2563eb"])
        fig.update_layout(xaxis_title=None, yaxis_title="loans")
        ui.chart(fig, 330)
    ui.note("The buyers file has 20,000 records for 720 sales (about 28 per sale), so these are best read as "
            "buyer <i>records</i> (enquiries / applicants) rather than one buyer per sale.")


# ================================================================ Agents
def agents():
    ui.header("🧑‍💼 Agent Dashboard", "Performance in this dataset alongside each agent's profile figures.")
    f = _filters()
    where, params = f.where("l")
    perf = q(f"""SELECT a.agent_id, a.name, a.rating, a.experience_years, a.commission_rate,
                        a.deals_closed AS deals_closed_lifetime, a.avg_closing_days,
                        COUNT(l.listing_id) AS listings, COUNT(l.sale_id) AS sales,
                        SUM(l.status = 'Active') AS active_listings,
                        COALESCE(SUM(l.sale_price), 0) AS revenue,
                        AVG(l.days_on_market) AS avg_days_on_market,
                        COALESCE(SUM(l.sale_price * a.commission_rate / 100.0), 0) AS commission_earned
                 FROM agents a JOIN v_listing_details l ON l.agent_id = a.agent_id {where}
                 GROUP BY a.agent_id ORDER BY revenue DESC""", params)
    _filter_banner()
    if perf.empty:
        st.info("No agents match these filters.")
        return
    c = st.columns(4)
    c[0].metric("Agents", len(perf))
    c[1].metric("Sales closed", ui.number(perf["sales"].sum()))
    c[2].metric("Sales revenue", ui.money(perf["revenue"].sum()))
    c[3].metric("Commission earned", ui.money(perf["commission_earned"].sum()))

    top_by = st.radio("Rank top 10 by", ["revenue", "sales", "commission_earned", "active_listings"],
                      horizontal=True, key="agent_rank",
                      format_func=lambda s: s.replace("_", " ").capitalize())
    top = perf.sort_values(top_by, ascending=False).head(10)
    fig = px.bar(top, x=top_by, y="agent_id", orientation="h", title=f"Top 10 agents by {top_by.replace('_', ' ')}",
                 color_discrete_sequence=[ui.BRICK],
                 text=top[top_by].map(ui.money) if top_by in ("revenue", "commission_earned") else top[top_by])
    fig.update_yaxes(autorange="reversed", title=None)
    ui.chart(fig, 380)

    c1, c2 = st.columns(2)
    with c1:
        fig = px.scatter(perf, x="experience_years", y="deals_closed_lifetime", size="sales", hover_name="agent_id",
                         trendline=None, title="Experience vs lifetime deals closed (bubble = sales here)",
                         color_discrete_sequence=[ui.BRICK])
        r = perf["experience_years"].corr(perf["deals_closed_lifetime"])
        ui.chart(fig, 340)
        st.caption(f"Pearson r = {r:.2f}: {'weak' if abs(r) < 0.3 else 'moderate' if abs(r) < 0.6 else 'strong'} "
                   f"{'positive' if r > 0 else 'negative'} relationship.")
    with c2:
        fig = px.scatter(perf, x="rating", y="avg_closing_days", hover_name="agent_id", size="sales",
                         title="Rating vs average closing days (profile)", color_discrete_sequence=["#2563eb"])
        r = perf["rating"].corr(perf["avg_closing_days"])
        ui.chart(fig, 340)
        st.caption(f"Pearson r = {r:.2f}: a higher rating does {'not ' if r > -0.3 else ''}mean faster closing.")

    st.subheader("Agent profile")
    pick = st.selectbox("Choose an agent (type to search)", perf["agent_id"] + " · " + perf["name"],
                        key="agent_pick")
    agent_id = pick.split(" · ")[0]
    row = perf.set_index("agent_id").loc[agent_id]
    c = st.columns(6)
    c[0].metric("Rating", f"{row.rating:.1f} / 5")
    c[1].metric("Experience", f"{row.experience_years} yrs")
    c[2].metric("Commission rate", f"{row.commission_rate:.2f}%")
    c[3].metric("Listings · sold", f"{row.listings:,} · {row.sales}")
    c[4].metric("Revenue", ui.money(row.revenue))
    c[5].metric("Avg days on market", ui.number(row.avg_days_on_market, 1))
    sales = q(f"""SELECT listing_id, city, property_type, price AS list_price, sale_price, date_listed, date_sold,
                         days_on_market
                  FROM v_listing_details l {where}{' AND ' if where else 'WHERE '}l.agent_id = ? AND status = 'Sold'
                  ORDER BY date_sold""", params + (agent_id,))
    st.markdown(f"**Sales closed by {agent_id}** ({len(sales)})")
    ui.table(sales, height=260)

    with st.expander("Full agent leaderboard"):
        ui.table(perf.round(2))


# ================================================================ SQL insights
def sql_insights():
    ui.header("🧮 SQL Insights",
              "The 30 business questions from the brief. Open a question to see its SQL, the live result, a chart "
              "and the finding. Queries live in sql/queries.sql and run against the current database.")
    queries = data.business_queries()
    categories = list(dict.fromkeys(x["category"] for x in queries))
    counts = {c: sum(x["category"] == c for x in queries) for c in categories}
    cat = st.selectbox("Category", categories, format_func=lambda c: f"{c} ({counts[c]} questions)",
                       key="sql_category")
    shown = [x for x in queries if x["category"] == cat]
    for item in shown:
        with st.expander(f"**{item['id']}** · {item['question']}"):
            result = q(item["sql"])
            st.markdown(f"<span class='bv-pill'>{item['category']}</span>"
                        f"<span class='bv-pill'>{len(result):,} rows</span>", unsafe_allow_html=True)
            if item["insight"]:
                ui.note(f"<b>Finding:</b> {item['insight']}")
            st.code(item["sql"], language="sql")
            fig = ui.chart_from_hint(result, item["chart"])
            if fig is not None:
                ui.chart(fig, 340, key=f"chart_{item['id']}")
            ui.table(result, height=min(400, 38 + 35 * len(result)))

    st.divider()
    st.subheader("Run your own query")
    st.caption("Read-only: SELECT / WITH statements only. Tables: agents, listings, property_attributes, sales, "
               "buyers. Views: v_listing_details, v_active_listings, v_sale_details, v_buyer_details, "
               "v_agent_performance, v_city_summary.")
    sql = st.text_area("SQL", "SELECT * FROM v_city_summary;", height=120, key="custom_sql")
    if st.button("▶ Run query", type="primary"):
        try:
            result = data.run_readonly(sql)
            st.success(f"{len(result):,} rows")
            ui.table(result.head(5000))
        except Exception as e:  # noqa: BLE001 (show any SQL error to the user)
            st.error(str(e))


# ================================================================ CRUD
def crud():
    ui.header("🛠️ Data Management", "Create, read, update and delete records in every table. Foreign keys, "
                                    "unique keys and CHECK constraints are enforced by SQLite.")
    table = st.selectbox("Table", list(data.TABLE_LABELS), format_func=data.TABLE_LABELS.get, key="crud_table")
    pk = data.primary_key(table)
    count = scalar(f"SELECT COUNT(*) FROM {table}")
    st.caption(f"`{table}` · {count:,} records · primary key `{pk}`")
    tab_view, tab_add, tab_upd, tab_del = st.tabs(["📖 View", "➕ Add", "✏️ Update", "🗑️ Delete"])

    with tab_view:
        search = st.text_input(f"Filter by {pk} (contains)", key=f"crud_search_{table}").strip()
        frame = q(f"SELECT * FROM {table} WHERE CAST({pk} AS TEXT) LIKE ? ORDER BY {pk}", (f"%{search}%",))
        ui.paged_table(frame, key=f"crud_{table}")

    with tab_add:
        _record_form(table, mode="add")

    with tab_upd:
        key = _pick_key(table, "upd")
        if key is not None:
            _record_form(table, mode="update", key=key)

    with tab_del:
        key = _pick_key(table, "del")
        if key is not None:
            row = data.get_row(table, key)
            ui.table(pd.DataFrame([row]))
            impact = data.delete_impact(table, key)
            if impact:
                st.warning("This delete also affects: " + "; ".join(f"{n:,} {t} row(s) {e}" for t, n, e in impact))
            confirm = st.checkbox(f"I understand that {pk} = {key} will be permanently deleted",
                                  key=f"del_confirm_{table}_{key}")
            st.button("Delete record", type="primary", disabled=not confirm, key=f"del_btn_{table}",
                      on_click=_delete_record, args=(table, pk, key))

    _show_flash()
    st.divider()
    with st.expander("Restore the original data"):
        st.caption("Rebuilds the database from the cleaned CSVs in data/processed/, undoing every add, edit and delete.")
        if st.button("Restore original data", key="restore"):
            data.restore_original()
            _flash(True, "Database restored to the original cleaned data.")
            st.rerun()


def _delete_record(table, pk, key):
    ok, msg, _ = data.delete(table, key)
    _flash(ok, f"Deleted {pk} = {key}." if ok else msg)
    if ok:
        st.session_state.pop(f"pick_del_{table}", None)   # clear the ID box (allowed inside a callback)


def _pick_key(table, suffix):
    pk = data.primary_key(table)
    raw = st.text_input(f"{pk} of the record", key=f"pick_{suffix}_{table}",
                        placeholder="e.g. " + str(scalar(f"SELECT {pk} FROM {table} ORDER BY {pk} LIMIT 1"))).strip()
    if not raw:
        return None
    key = int(raw) if raw.isdigit() and table not in data.ID_PREFIX else raw.upper()
    if data.get_row(table, key) is None:
        st.error(f"No record with {pk} = {raw}.")
        return None
    return key


def _record_form(table, mode, key=None):
    cols = data.columns(table)
    pk = data.primary_key(table)
    current = data.get_row(table, key) if mode == "update" else {}
    fks = data.FOREIGN_KEYS.get(table, {})
    tag = key if mode == "update" else data.next_id(table)   # fresh widget keys after each insert
    with st.form(f"form_{mode}_{table}_{tag}", clear_on_submit=(mode == "add")):
        values = {}
        grid = st.columns(3)
        for i, (name, sqltype, notnull, is_pk) in enumerate(cols):
            box = grid[i % 3]
            label = name + (" *" if notnull or is_pk else "") + (f"  →{fks[name][0]}" if name in fks else "")
            value = current.get(name) if current else None
            if is_pk:
                box.text_input(label, str(tag), disabled=True, key=f"{mode}_{table}_{name}_{tag}")
                values[name] = tag
            elif name in data.FLAGS:
                values[name] = int(box.checkbox(name, bool(value), key=f"{mode}_{table}_{name}_{tag}"))
            elif name in data.ENUMS:
                options = data.ENUMS[name]
                index = options.index(value) if value in options else 0
                values[name] = box.selectbox(label, options, index=index, key=f"{mode}_{table}_{name}_{tag}",
                                             format_func=lambda o: "— none —" if o is None else o)
            elif name in data.DATES:
                d = dt.date.fromisoformat(value) if value else dt.date.today()
                values[name] = box.date_input(label, d, key=f"{mode}_{table}_{name}_{tag}").isoformat()
            elif sqltype in ("REAL", "INTEGER") and name not in fks:
                step = 1.0 if sqltype == "INTEGER" else 0.01
                num = box.number_input(label, value=float(value) if value is not None and pd.notna(value) else 0.0,
                                       step=step, format="%.0f" if sqltype == "INTEGER" else "%.2f",
                                       key=f"{mode}_{table}_{name}_{tag}")
                values[name] = int(num) if sqltype == "INTEGER" else float(num)
            else:
                text = box.text_input(label, "" if value is None or pd.isna(value) else str(value),
                                      key=f"{mode}_{table}_{name}_{tag}").strip()
                if name in fks and sqltype == "INTEGER":
                    values[name] = int(text) if text.isdigit() else (text or None)
                else:
                    values[name] = text or None
        submitted = st.form_submit_button("Add record" if mode == "add" else "Save changes", type="primary")
    if submitted:
        missing = [n for n, _, notnull, is_pk in cols if notnull and not is_pk and values.get(n) in (None, "")]
        if missing:
            st.error("Required: " + ", ".join(missing))
            return
        if mode == "add":
            ok, msg, _ = data.insert(table, values)
            _flash(ok, f"Added {pk} = {values[pk]}." if ok else msg)
        else:
            changes = {k: v for k, v in values.items() if k != pk and v != _normalise(current.get(k))}
            if not changes:
                st.info("Nothing changed.")
                return
            ok, msg, _ = data.update(table, key, changes)
            _flash(ok, f"Updated {pk} = {key}: {', '.join(changes)}." if ok else msg)
        st.rerun()


def _normalise(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _flash(ok, message):
    st.session_state["flash"] = (ok, message)


def _show_flash():
    flash = st.session_state.pop("flash", None)
    if flash:
        (st.success if flash[0] else st.error)(flash[1])
        if flash[0]:
            st.toast(flash[1], icon="✅")


# ================================================================ About
ER_DIAGRAM = """
digraph {
  graph [rankdir=LR, bgcolor="transparent", pad=0.2, nodesep=0.4, ranksep=0.9]
  node  [shape=plain, fontname="Helvetica", fontsize=11]
  edge  [color="#b4532a", arrowhead=crow, arrowtail=tee, dir=both, fontname="Helvetica", fontsize=9]
  agents [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4" bgcolor="white">
    <tr><td bgcolor="#b4532a"><font color="white"><b>agents</b></font></td></tr>
    <tr><td align="left"><b>agent_id</b> PK</td></tr><tr><td align="left">name, phone, email</td></tr>
    <tr><td align="left">commission_rate, rating</td></tr><tr><td align="left">deals_closed, experience_years</td></tr>
    <tr><td align="left">avg_closing_days</td></tr></table>>]
  listings [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4" bgcolor="white">
    <tr><td bgcolor="#b4532a"><font color="white"><b>listings</b></font></td></tr>
    <tr><td align="left"><b>listing_id</b> PK</td></tr><tr><td align="left">agent_id FK</td></tr>
    <tr><td align="left">city, property_type</td></tr><tr><td align="left">price, area_sqft, date_listed</td></tr>
    <tr><td align="left">latitude, longitude</td></tr></table>>]
  attrs [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4" bgcolor="white">
    <tr><td bgcolor="#b4532a"><font color="white"><b>property_attributes</b></font></td></tr>
    <tr><td align="left"><b>attribute_id</b> PK</td></tr><tr><td align="left">listing_id FK, UNIQUE</td></tr>
    <tr><td align="left">bedrooms, bathrooms, floors</td></tr><tr><td align="left">year_built, furnishing</td></tr>
    <tr><td align="left">rented, tenants, metro_km</td></tr><tr><td align="left">parking, power_backup</td></tr></table>>]
  sales [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4" bgcolor="white">
    <tr><td bgcolor="#b4532a"><font color="white"><b>sales</b></font></td></tr>
    <tr><td align="left"><b>sale_id</b> PK</td></tr><tr><td align="left">listing_id FK, UNIQUE</td></tr>
    <tr><td align="left">sale_price, date_sold</td></tr><tr><td align="left">days_on_market</td></tr></table>>]
  buyers [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4" bgcolor="white">
    <tr><td bgcolor="#b4532a"><font color="white"><b>buyers</b></font></td></tr>
    <tr><td align="left"><b>buyer_id</b> PK</td></tr><tr><td align="left">sale_id FK</td></tr>
    <tr><td align="left">buyer_type, payment_mode</td></tr><tr><td align="left">loan_taken, provider, amount</td></tr></table>>]
  agents -> listings [label="1 : many"]
  listings -> attrs [label="1 : 1", arrowhead=tee]
  listings -> sales [label="1 : 0..1", arrowhead=teeodot]
  sales -> buyers [label="1 : many"]
}
"""


def about():
    ui.header("ℹ️ About BrickView")
    ui.md("""
**BrickView** turns five raw real-estate files into a clean, normalised SQLite database and a Streamlit
dashboard for buyers, investors and agents: pricing trends, time on market, agent performance and buyer
financing, all driven by SQL.

**Pipeline:** raw JSON / CSV → `src/clean.py` (types, dates, booleans, keys, fixes; every step logged) →
cleaned CSVs in `data/processed/` → `sql/schema.sql` (tables, foreign keys, CHECK constraints, 10 indexes,
6 views) → `db/brickview.db` → this app. Rebuild everything with `python pipeline.py`.
""")
    st.subheader("Database schema")
    st.graphviz_chart(ER_DIAGRAM, width="stretch")
    log = pd.read_csv(config.PROCESSED_DIR / "cleaning_log.csv")
    with st.expander("Cleaning log (what the pipeline changed)"):
        ui.table(log)

    st.subheader("Data notes")
    ui.md("""
The data is synthetic coursework data. These quirks were found during cleaning and are handled or flagged:

- **Coordinates don't match cities.** Every city's points are spread over the whole continental US
  (lat 25-49, lon -125 to -67). The listings map shows them as given; the city-summary map uses real city centres.
- **Two listing populations.** Only listings L00001-L01200 have sales (720 sold). The other 20,000 listings
  were added later with a wider price range ($0.1M-5M vs $0.1M-2M) and none are sold, so average *sale*
  prices ($1.08M) are much lower than average *list* prices ($2.45M).
- **Buyers.** The raw `sale_id` column holds listing IDs; it was mapped to the real `sales.sale_id`. There are
  20,000 buyer records for 720 sales (about 28 each), and 93% of loans are larger than the sale price,
  so loan amounts are not realistic.
- **Agents.** `deals_closed` is a lifetime profile figure (average 137) and doesn't match sales in this data
  (average 14 per agent). Both are shown where relevant.
- **Fixes applied:** `days_on_market` stored as whole days (it equals the date gap to within 0.03 days);
  255 rows with floor number above total floors were swapped; booleans stored as 0/1.
- **Left as-is (flagged):** 467 non-rented homes have tenants and 2,067 rented homes have 0 tenants.
- **Currency:** US cities, so prices are shown in US dollars (the buyer data uses Indian banks and UPI).
""")
    st.subheader("Tech stack")
    st.markdown("Python · pandas · SQLite (SQL views, indexes, window functions) · Streamlit · Plotly")
    st.subheader("Author")
    st.markdown(f"**{config.AUTHOR}** · [{config.AUTHOR_EMAIL}](mailto:{config.AUTHOR_EMAIL}) · "
                f"[GitHub repository]({config.GITHUB_URL})")
