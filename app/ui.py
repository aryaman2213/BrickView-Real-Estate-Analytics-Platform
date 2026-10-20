"""Styling, number formatting and chart helpers shared by every page."""
import math

import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st

import config

BRICK = "#b4532a"
INK = "#1f2937"
MUTED = "#6b7280"
# Categorical palette (colour-blind safe ordering), one colour per property type / city.
PALETTE = ["#b4532a", "#2563eb", "#0f766e", "#a16207", "#7c3aed", "#be185d", "#475569"]
TYPE_COLORS = dict(zip(config.PROPERTY_TYPES, PALETTE))
CITY_COLORS = dict(zip(config.CITIES, PALETTE))

pio.templates["brickview"] = pio.templates["plotly_white"]
pio.templates["brickview"].layout.update(
    font=dict(family="Inter, system-ui, sans-serif", size=13, color=INK),
    colorway=PALETTE, margin=dict(l=10, r=10, t=40, b=10),
    title=dict(font=dict(size=15)), hoverlabel=dict(font_size=12),
    xaxis=dict(gridcolor="#eef0f3"), yaxis=dict(gridcolor="#eef0f3"),
)
pio.templates.default = "brickview"

CSS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1350px;}
[data-testid="stMetric"] {background: #fff; border: 1px solid #ece7e2; border-radius: 12px;
    padding: 14px 16px; box-shadow: 0 1px 2px rgba(0,0,0,.04);}
[data-testid="stMetricLabel"] p {font-size: .82rem; color: #6b7280;}
[data-testid="stMetricValue"] {font-size: 1.55rem;}
.bv-hero {background: linear-gradient(135deg, #7c2d12 0%, #b4532a 55%, #d97706 100%); color: #fff;
    border-radius: 16px; padding: 28px 30px; margin-bottom: 18px;}
.bv-hero h1 {color: #fff; margin: 0 0 6px 0; font-size: 2.1rem;}
.bv-hero p {color: #fde7d9; margin: 0; font-size: 1.02rem;}
.bv-note {background: #fff7ed; border-left: 4px solid #b4532a; padding: 10px 14px; border-radius: 6px;
    color: #431407; font-size: .92rem; margin: 6px 0 12px 0;}
.bv-pill {display: inline-block; background: #f3e8e2; color: #7c2d12; border-radius: 999px;
    padding: 2px 10px; font-size: .78rem; margin-right: 6px;}
</style>
"""


def setup_page():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(f'<div class="bv-hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def md(text):
    """Markdown with dollar signs escaped (Streamlit renders $...$ as LaTeX)."""
    st.markdown(text.replace("$", r"\$"))


def note(text):
    st.markdown(f'<div class="bv-note">{text.replace("$", "&#36;")}</div>', unsafe_allow_html=True)


def header(title, caption=None):
    st.title(title)
    if caption:
        st.caption(caption)


# ---------------------------------------------------------------- formatting
def money(value, short=True):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    if short:
        for size, suffix in [(1e9, "B"), (1e6, "M"), (1e3, "K")]:
            if abs(value) >= size:
                return f"{config.CURRENCY}{value / size:,.2f}{suffix}"
    return f"{config.CURRENCY}{value:,.0f}"


def number(value, decimals=0):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    return f"{value:,.{decimals}f}"


def pct(value, decimals=1):
    return "–" if value is None else f"{value:.{decimals}f}%"


MONEY_COLUMNS = ("price", "revenue", "commission", "loan_amount", "sale_price", "list_price")


def column_config(frame):
    """Readable st.dataframe column formats: money columns with $, ratios with 4 dp."""
    cfg = {}
    for col in frame.columns:
        name = col.lower()
        if any(k in name for k in MONEY_COLUMNS) and pd.api.types.is_numeric_dtype(frame[col]):
            cfg[col] = st.column_config.NumberColumn(col, format="dollar")
        elif "ratio" in name:
            cfg[col] = st.column_config.NumberColumn(col, format="%.4f")
        elif name.startswith("pct") or name.endswith("_pct"):
            cfg[col] = st.column_config.NumberColumn(col, format="%.2f%%")
    return cfg


def table(frame, height=None, **kwargs):
    st.dataframe(frame, width="stretch", hide_index=True, height=height or "auto",
                 column_config=column_config(frame), **kwargs)


def paged_table(frame, key, page_size=25):
    """st.dataframe with pagination (sorting is built in: click a column header)."""
    total = len(frame)
    pages = max(1, math.ceil(total / page_size))
    c1, c2, c3 = st.columns([1, 1, 3])
    size = c1.selectbox("Rows per page", [25, 50, 100, 250], key=f"{key}_size",
                        index=[25, 50, 100, 250].index(page_size))
    pages = max(1, math.ceil(total / size))
    page = c2.number_input("Page", 1, pages, 1, key=f"{key}_page")
    start = (page - 1) * size
    c3.markdown(f"<div style='padding-top:2rem;color:{MUTED}'>Rows {start + 1 if total else 0:,}–"
                f"{min(start + size, total):,} of {total:,} · click a column header to sort</div>",
                unsafe_allow_html=True)
    table(frame.iloc[start:start + size])


def chart(fig, height=380, key=None):
    fig.update_layout(height=height)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False}, key=key)


def chart_from_hint(frame, hint, title=None):
    """Draw a plotly chart from a queries.sql hint such as 'bar x=city y=avg_list_price'."""
    from src.db import parse_chart

    kind, opts = parse_chart(hint)
    if kind is None or frame.empty:
        return None
    frame = frame.copy()
    for axis in ("x", "y", "names"):   # strip the '1. ' sort prefixes used in band labels
        col = opts.get(axis)
        if col in frame and frame[col].dtype == object:
            frame[col] = frame[col].str.replace(r"^\d+\.\s", "", regex=True)
    color = opts.get("color")
    if color in frame:
        frame[color] = frame[color].astype(str)
    if kind == "bar":
        horizontal = opts.get("orientation") == "h"
        fig = px.bar(frame, x=opts["x"], y=opts["y"], color=color, barmode="group",
                     orientation="h" if horizontal else "v", title=title,
                     color_discrete_sequence=PALETTE)
        if horizontal:
            fig.update_yaxes(autorange="reversed", type="category")
        else:
            fig.update_xaxes(type="category")
        if not color:
            fig.update_traces(marker_color=BRICK)
    elif kind == "line":
        fig = px.line(frame, x=opts["x"], y=opts["y"], markers=True, title=title)
        fig.update_traces(line_color=BRICK)
    elif kind == "pie":
        fig = px.pie(frame, names=opts["names"], values=opts["values"], hole=0.5, title=title,
                     color_discrete_sequence=PALETTE)
    else:
        return None
    return fig
