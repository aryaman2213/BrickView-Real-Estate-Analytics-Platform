"""Capture dashboard screenshots into reports/screenshots/ (needs the app running and Playwright).

    streamlit run app/streamlit_app.py --server.port 8541 &
    python reports/take_screenshots.py --url http://localhost:8541
"""
import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "screenshots"

# (file name, url path, optional tab / expander label to click, scroll pixels)
SHOTS = [
    ("01_overview", "", None, 0),
    ("02_market_explorer", "explorer", None, 0),
    ("03_map", "visualizations", None, 330),
    ("04_market_charts", "visualizations", "Market", 0),
    ("05_sales_trend", "visualizations", "Sales trend", 0),
    ("06_buyers_financing", "visualizations", "Buyers & financing", 0),
    ("07_agent_dashboard", "agents", None, 0),
    ("08_sql_insights", "sql-insights", "Q01", 150),
    ("09_data_management", "data-management", "Add", 0),
    ("10_about_schema", "about", None, 0),
]


def settle(page):
    page.wait_for_selector("[data-testid='stApp']")
    time.sleep(1.5)
    page.wait_for_function("!document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=60_000)
    time.sleep(2.5)


def main(url):
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1.5)
        for name, path, click, scroll in SHOTS:
            page.goto(f"{url}/{path}")
            settle(page)
            if click:
                target = (page.locator("summary", has_text=click) if click.startswith("Q")
                          else page.get_by_role("tab", name=click))
                target.first.scroll_into_view_if_needed()
                target.first.click()
                settle(page)
            if scroll:
                page.mouse.move(800, 500)
                page.mouse.wheel(0, scroll)
                page.mouse.move(5, 5)   # park the cursor so no hover tooltip is captured
                time.sleep(2.5)
            page.screenshot(path=str(OUT / f"{name}.png"))
            print("saved", name)
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8541")
    main(parser.parse_args().url)
