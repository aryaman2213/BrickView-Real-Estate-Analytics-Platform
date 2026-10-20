"""Build the project report (HTML -> PDF).

Every number, query and table is read from db/brickview.db, sql/queries.sql and data/processed/,
so the report always matches the analysis. The PDF is printed with headless Chrome through
Playwright (pip install playwright).

    python reports/build_report.py
"""
import argparse
import base64
import html
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src import db  # noqa: E402

REPORTS = ROOT / "reports"
BUILD = REPORTS / "_build"
PDF_PATH = REPORTS / "BrickView_Project_Report.pdf"

CSS = """
@page { size: A4; }
body { font-family: Inter, Helvetica, Arial, sans-serif; color: #1f2937; font-size: 10pt; line-height: 1.5; }
h1 { font-size: 26pt; margin: 0 0 6px; color: #7c2d12; }
h2 { font-size: 15pt; color: #7c2d12; border-bottom: 2px solid #f3e8e2; padding-bottom: 4px; margin-top: 26px; }
h3 { font-size: 11pt; margin: 16px 0 4px; }
.cover { background: linear-gradient(135deg, #7c2d12, #b4532a 55%, #d97706); color: #fff; padding: 34px 32px;
         border-radius: 14px; margin-bottom: 18px; }
.cover h1 { color: #fff; } .cover p { color: #fde7d9; margin: 4px 0; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 12px 0; }
.kpi { border: 1px solid #ece7e2; border-radius: 10px; padding: 8px 10px; }
.kpi b { display: block; font-size: 14pt; } .kpi span { color: #6b7280; font-size: 8.5pt; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 10px; font-size: 8.5pt; }
th { background: #f3e8e2; text-align: left; padding: 4px 6px; }
td { border-bottom: 1px solid #eee; padding: 3px 6px; }
td.n { text-align: right; font-variant-numeric: tabular-nums; }
pre { background: #f8f6f4; border: 1px solid #eee; border-radius: 6px; padding: 8px; font-size: 7.6pt;
      white-space: pre-wrap; page-break-inside: avoid; }
.q { page-break-inside: avoid; margin-bottom: 14px; }
.answer { background: #fff7ed; border-left: 4px solid #b4532a; padding: 6px 10px; border-radius: 4px; }
.shot { width: 100%; border: 1px solid #ddd; border-radius: 8px; margin: 6px 0 2px; }
.cap { color: #6b7280; font-size: 8.5pt; margin-bottom: 12px; }
.figs { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.figs img { width: 100%; }
.break { page-break-before: always; }
a { color: #b4532a; }
"""


def esc(x):
    return html.escape(str(x))


def fmt(value, column):
    if pd.isna(value):
        return "–"
    if isinstance(value, float):
        if any(k in column for k in ("price", "revenue", "commission", "loan_amount")):
            return f"${value:,.2f}"
        if "ratio" in column:
            return f"{value:.4f}"
        return f"{value:,.2f}"
    if isinstance(value, int) and "year" not in column:
        return f"{value:,}"
    return esc(value)


def table(frame, max_rows=None):
    shown = frame.head(max_rows) if max_rows else frame
    head = "".join(f"<th>{esc(c)}</th>" for c in frame.columns)
    rows = "".join(
        "<tr>" + "".join(f'<td class="{"n" if isinstance(v, (int, float)) else ""}">{fmt(v, c)}</td>'
                         for c, v in zip(frame.columns, r)) + "</tr>"
        for r in shown.itertuples(index=False))
    note = f'<div class="cap">Showing {len(shown)} of {len(frame):,} rows.</div>' if len(shown) < len(frame) else ""
    return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>{note}"


def img(path, cls="shot"):
    data = base64.b64encode(Path(path).read_bytes()).decode()
    return f'<img class="{cls}" src="data:image/png;base64,{data}">'


def build_html(github, live):
    k = db.query("""SELECT (SELECT COUNT(*) FROM listings) listings, (SELECT COUNT(*) FROM sales) sales,
                           (SELECT COUNT(*) FROM v_active_listings) active, (SELECT AVG(price) FROM listings) avg_price,
                           (SELECT SUM(sale_price) FROM sales) revenue, (SELECT AVG(days_on_market) FROM sales) dom,
                           (SELECT COUNT(*) FROM agents) agents, (SELECT COUNT(*) FROM buyers) buyers""").iloc[0]
    counts = {t: int(db.query(f"SELECT COUNT(*) n FROM {t}")["n"][0]) for t in config.TABLE_ORDER}
    log = pd.read_csv(config.PROCESSED_DIR / "cleaning_log.csv")
    objects = db.query("SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND type != 'table'")
    queries = db.load_queries()
    p = []

    p.append(f"""<div class="cover"><h1>BrickView: Real Estate Analytics Platform</h1>
    <p>Project report · Python, SQL (SQLite), Streamlit · {esc(config.AUTHOR)}</p>
    <p>Live app: <a style="color:#fff" href="{live}">{live}</a></p>
    <p>Code: <a style="color:#fff" href="{github}">{github}</a></p></div>""")
    p.append('<div class="kpis">' + "".join(
        f'<div class="kpi"><b>{v}</b><span>{l}</span></div>' for l, v in [
            ("Listings", f"{k.listings:,.0f}"), ("Active (unsold)", f"{k.active:,.0f}"), ("Sales", f"{k.sales:,.0f}"),
            ("Sales revenue", f"${k.revenue / 1e6:,.1f}M"), ("Avg list price", f"${k.avg_price / 1e6:,.2f}M"),
            ("Avg days on market", f"{k.dom:.1f}"), ("Agents", f"{k.agents:.0f}"),
            ("Buyer records", f"{k.buyers:,.0f}")]) + "</div>")

    p.append("""<h2>1. Problem and approach</h2>
    <p>Buyers, sellers and agents lack an accessible way to monitor pricing, time on market and sales performance.
    BrickView answers that with a SQL-backed dashboard: five raw files are cleaned, stored in a normalised SQLite
    database, analysed with 30 SQL queries, and served through a Streamlit app with filters, maps, charts,
    an agent dashboard, a SQL insights page and full CRUD on every table.</p>
    <p><b>Pipeline:</b> raw JSON / CSV &rarr; <code>src/clean.py</code> &rarr; cleaned CSVs (<code>data/processed/</code>)
    &rarr; <code>sql/schema.sql</code> &rarr; <code>db/brickview.db</code> &rarr; Streamlit (<code>app/</code>).
    One command rebuilds everything: <code>python pipeline.py</code>. 43 automated tests (<code>pytest</code>) check
    row counts, integrity, all 30 queries, answers against pandas, filters and CRUD.</p>""")

    p.append("<h2>2. Data preparation</h2>")
    p.append(table(pd.DataFrame({"table": list(counts), "rows": list(counts.values()),
                                 "source file": [config.RAW_FILES[t] for t in counts]})))
    p.append("<h3>Cleaning log</h3>" + table(log))
    p.append("""<h3>Data-quality findings</h3><ul>
    <li><b>Buyer keys:</b> the raw <code>sale_id</code> column holds listing IDs; it was mapped to the real <code>sales.sale_id</code>.</li>
    <li><b>Buyer volume:</b> 20,000 buyer records for 720 sales (about 28 per sale), and 93% of loans exceed the sale price,
        so buyer figures are read as records and loan amounts as unrealistic.</li>
    <li><b>Coordinates</b> are random points across the continental US for every city; the app adds a city-summary map at real city centres.</li>
    <li><b>Two listing populations:</b> only L00001-L01200 have sales ($0.1M-2M); the other 20,000 listings reach $5M and are all unsold.</li>
    <li><b>days_on_market</b> equals the listing-to-sale date gap to within 0.03 days and is stored as whole days.</li>
    <li>255 rows with floor number above total floors were swapped; 467 non-rented homes with tenants and 2,067 rented homes with 0 tenants are flagged.</li>
    <li><b>Agents:</b> <code>deals_closed</code> is a lifetime figure (average 137) and doesn't match sales in the data (average 14).</li></ul>""")

    p.append('<h2 class="break">3. Database design</h2>')
    p.append("""<p>Five tables in third normal form. <b>agents</b> 1&rarr;many <b>listings</b>;
    <b>listings</b> 1&rarr;1 <b>property_attributes</b> (UNIQUE listing_id); <b>listings</b> 1&rarr;0..1 <b>sales</b>
    (UNIQUE listing_id); <b>sales</b> 1&rarr;many <b>buyers</b>. Foreign keys are enforced (<code>PRAGMA foreign_keys = ON</code>)
    with <code>ON DELETE CASCADE</code> (and <code>SET NULL</code> for a deleted agent). CHECK constraints guard prices,
    ratings, dates, flags and categories.</p>""")
    for t in config.TABLE_ORDER:
        cols = db.table_columns(t)
        frame = pd.DataFrame([(n, ty, "yes" if nn else "", "yes" if pk else "") for n, ty, nn, pk in cols],
                             columns=["column", "type", "not null", "primary key"])
        p.append(f"<h3>{t}</h3>" + table(frame))
    p.append("<h3>Indexes and views</h3>" + table(objects))

    p.append('<h2 class="break">4. Streamlit application</h2>')
    shots = sorted((REPORTS / "screenshots").glob("*.png"))
    captions = {
        "01": "Overview: KPIs, key findings and navigation.",
        "02": "Market Explorer: sidebar filters (city, type, price, agent, listed/sale date, status, bedrooms, furnishing), paged sortable table, CSV export.",
        "03": "Interactive map of listings coloured by property type, with hover details; a city-summary bubble view is also available.",
        "04": "Market charts: listings / average price by city, property-type pie, price distribution, price per sq ft.",
        "05": "Monthly new listings vs sales, days on market by type, sale-to-list distribution.",
        "06": "Buyer and financing behaviour.",
        "07": "Agent dashboard: leaderboard, experience and rating vs performance, per-agent profile.",
        "08": "SQL Insights: every question in a drop-down with its SQL, live output, chart and finding.",
        "09": "Data Management: create, read, update and delete for all five tables, with constraint checks.",
        "10": "About: schema diagram, cleaning log and data notes.",
    }
    for s in shots:
        p.append(img(s) + f'<div class="cap">{esc(captions.get(s.name[:2], s.stem))}</div>')

    p.append('<h2 class="break">5. SQL analysis: 30 business questions</h2>')
    section = None
    for q in queries:
        if q["category"] != section:
            section = q["category"]
            p.append(f"<h3 style='font-size:12.5pt;color:#7c2d12'>{esc(section)}</h3>")
        result = db.query(q["sql"])
        p.append(f'<div class="q"><h3>{q["id"]}. {esc(q["question"])}</h3><pre>{esc(q["sql"])}</pre>'
                 f'{table(result, 10)}<div class="answer"><b>Answer:</b> {esc(q["insight"])}</div></div>')

    figs = sorted((REPORTS / "figures").glob("q*.png"))
    p.append('<h2 class="break">6. Selected charts</h2><div class="figs">' + "".join(img(f, "") for f in figs) + "</div>")

    p.append("""<h2>7. Key insights and recommendations</h2><ol>
    <li><b>Price to the market, not above it:</b> sale-to-list is within 0.2% of 1.00 everywhere and half of homes sell below list.</li>
    <li><b>New York commands the highest prices</b> ($2.49M average), but the city spread is only 2.6%.</li>
    <li><b>Houses move fastest</b> (58 days) and condos slowest (67); Houston is the fastest market, Los Angeles the slowest.
        Agents should expect longer campaigns for condos in LA and Chicago.</li>
    <li><b>Amenities and location add little:</b> no metro premium, about 1% for furnishing, about 4% on sale price for parking + power backup.</li>
    <li><b>Demand peaked in October 2023</b> and has slowed since; 26% of sales took over 90 days, a pool worth targeting with price reviews.</li>
    <li><b>Ratings don't predict speed</b> and experience is only weakly linked to deals, so agent assignment should use measured
        days-on-market and revenue (Agent Dashboard) rather than profile ratings.</li>
    <li><b>Buyers are balanced:</b> 50/50 investors and end users, about half use a loan, and all payment modes are used equally.</li>
    <li><b>Data caveat:</b> the dataset is synthetic (uniform attributes, random coordinates, unrealistic loan sizes), so effects are small
        and should be re-checked on real market data.</li></ol>""")

    p.append(f"""<h2>8. Deliverables</h2><table><tbody>
    <tr><td>Cleaned CSV data</td><td><code>data/processed/*.csv</code> + <code>cleaning_log.csv</code></td></tr>
    <tr><td>SQL schema</td><td><code>sql/schema.sql</code> (source) and <code>sql/schema_dump.sql</code> (as stored)</td></tr>
    <tr><td>30 SQL queries</td><td><code>sql/queries.sql</code></td></tr>
    <tr><td>Analysis notebook</td><td><code>notebooks/eda.ipynb</code></td></tr>
    <tr><td>Streamlit app</td><td><code>app/</code> · <a href="{live}">{live}</a></td></tr>
    <tr><td>Tests</td><td><code>tests/test_brickview.py</code> (43 checks)</td></tr>
    <tr><td>Report and screenshots</td><td><code>reports/</code></td></tr></tbody></table>""")

    return (f'<!doctype html><html><head><meta charset="utf-8"><title>BrickView: Project Report</title>'
            f'<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">'
            f"<style>{CSS}</style></head><body>{''.join(p)}</body></html>")


def print_pdf(html_path, pdf_path):
    from playwright.sync_api import sync_playwright

    footer = ('<div style="font-size:7.5pt;color:#94a3b8;width:100%;padding:0 15mm;display:flex;'
              'justify-content:space-between;font-family:Helvetica,Arial,sans-serif"><span>BrickView · Project report</span>'
              '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page()
        page.goto(html_path.as_uri(), wait_until="networkidle")
        page.pdf(path=str(pdf_path), format="A4", print_background=True, display_header_footer=True,
                 header_template="<span></span>", footer_template=footer,
                 margin={"top": "15mm", "bottom": "18mm", "left": "14mm", "right": "14mm"})
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--github", default=config.GITHUB_URL)
    parser.add_argument("--live", default=config.LIVE_URL)
    args = parser.parse_args()
    BUILD.mkdir(exist_ok=True)
    html_path = BUILD / "report.html"
    html_path.write_text(build_html(args.github, args.live), encoding="utf-8")
    print_pdf(html_path, PDF_PATH)
    print(f"wrote {PDF_PATH.relative_to(ROOT)}")
