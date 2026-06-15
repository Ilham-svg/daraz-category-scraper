"""
Daraz Product Category Scraper - PLAYWRIGHT VERSION (FAST)
===========================================================
Uses Playwright (Chromium) to render JavaScript and extract breadcrumbs.
2-3x faster than Selenium.

Requirements:
  pip install playwright
  playwright install chromium
"""

import pandas as pd
import json
import time
import random
import os
import re
import html as html_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("ERROR: Playwright not installed.")
    print("Run: pip install playwright")
    print("Then: playwright install chromium")
    exit(1)

# ======================
# CONFIG
# ======================

INPUT_FILE   = "input_ids.xlsx"
OUTPUT_FILE  = "output_categories.xlsx"
MAX_WORKERS  = 3        # Playwright is lighter than Selenium
DELAY_MIN    = 1.5
DELAY_MAX    = 3.0
TIMEOUT      = 30
RESUME       = True

DARAZ_DOMAIN = "daraz.com.bd"


def extract_category_playwright(page, item_id):
    """Extract category using Playwright."""
    url = f"https://www.{DARAZ_DOMAIN}/products/-i{item_id}.html"

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT*1000)

        # Wait for breadcrumb to appear
        try:
            page.wait_for_selector("#J_breadcrumb", timeout=5000)
        except:
            pass

        # Additional wait for dynamic content
        time.sleep(2)

        # Method 1: Extract from breadcrumb <ul>
        breadcrumb_html = page.inner_html("#J_breadcrumb")
        if breadcrumb_html and len(breadcrumb_html) > 50:
            titles = []
            for m in re.finditer(r'<a[^>]*title\s*=\s*["\']([^"\']+)["\'][^>]*>', breadcrumb_html):
                title = m.group(1).strip()
                title = html_module.unescape(title)
                if title and title.lower() not in ("home", "\u09b9\u09cb\u09ae", "daraz", ""):
                    titles.append(title)
            if len(titles) >= 2:
                return " > ".join(titles)

        # Method 2: Query all <a> elements in breadcrumb
        links = page.query_selector_all("#J_breadcrumb a")
        if links:
            categories = []
            for link in links:
                title = link.get_attribute("title")
                if title:
                    text = html_module.unescape(title.strip())
                    if text and text.lower() not in ("home", "\u09b9\u09cb\u09ae", "daraz", ""):
                        categories.append(text)
            if len(categories) >= 2:
                return " > ".join(categories)

        # Method 3: data-spm breadcrumb
        links = page.query_selector_all("[data-spm='breadcrumb'] a")
        if links:
            categories = []
            for link in links:
                title = link.get_attribute("title")
                if title:
                    text = html_module.unescape(title.strip())
                    if text and text.lower() not in ("home", "\u09b9\u09cb\u09ae", "daraz", ""):
                        categories.append(text)
            if len(categories) >= 2:
                return " > ".join(categories)

        # Method 4: JSON-LD fallback
        scripts = page.query_selector_all('script[type="application/ld+json"]')
        for script in scripts:
            try:
                data = json.loads(script.inner_text())
                for obj in (data if isinstance(data, list) else [data]):
                    if obj.get("@type") == "Product":
                        cat = obj.get("category")
                        if cat:
                            return cat.strip()
            except:
                pass

        return None

    except Exception as e:
        return f"Error: {e}"


def process_batch(item_ids):
    """Process a batch of items in a single browser instance."""
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for item_id in item_ids:
            try:
                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                cat = extract_category_playwright(page, item_id)
                url = f"https://www.{DARAZ_DOMAIN}/products/-i{item_id}.html"
                results[item_id] = (url, cat or "No Category")
                print(f"  {item_id}: {cat}")
            except Exception as e:
                results[item_id] = (f"https://www.{DARAZ_DOMAIN}/products/-i{item_id}.html", f"Error: {e}")

        browser.close()

    return results


def load_existing():
    if RESUME and os.path.exists(OUTPUT_FILE):
        try:
            df = pd.read_excel(OUTPUT_FILE, dtype={"Product ID": str})
            done = df[
                ~df["Category Path"].astype(str).str.startswith("Error") &
                ~df["Category Path"].astype(str).str.startswith("404") &
                ~df["Category Path"].astype(str).str.startswith("No Category")
            ]
            return dict(zip(done["Product ID"], done["Category Path"]))
        except Exception:
            pass
    return {}


def run():
    df = pd.read_excel(INPUT_FILE, dtype={"Product ID": str})

    if "Product ID" not in df.columns:
        raise ValueError(f"'{INPUT_FILE}' must contain a 'Product ID' column.")

    prior_cats = load_existing()

    if prior_cats:
        print(f"Resuming — {len(prior_cats)} rows already done.\n")

    pending = df[~df["Product ID"].isin(prior_cats)].copy()
    print(f"Processing {len(pending)} / {len(df)} rows with Playwright...\n")

    # Process in batches (one browser per batch)
    batch_size = 10  # Process 10 items per browser instance
    item_ids = pending["Product ID"].astype(str).tolist()
    batches = [item_ids[i:i+batch_size] for i in range(0, len(item_ids), batch_size)]

    all_results = {}

    for i, batch in enumerate(batches):
        print(f"\nBatch {i+1}/{len(batches)}: {len(batch)} items")
        results = process_batch(batch)
        all_results.update(results)

    # Rebuild output
    output_rows = []
    for _, row in df.iterrows():
        pid = str(row["Product ID"]).strip()
        if pid in all_results:
            url, cat = all_results[pid]
        else:
            url = f"https://www.{DARAZ_DOMAIN}/products/-i{pid}.html"
            cat = prior_cats.get(pid, "")
        output_rows.append({
            "Product ID": pid,
            "Product URL": url,
            "Category Path": cat,
        })

    out = pd.DataFrame(output_rows)
    out.to_excel(OUTPUT_FILE, index=False)

    total = len(out)
    found = out["Category Path"].str.contains(" > ", na=False).sum()
    errors = out["Category Path"].str.startswith("Error", na=False).sum()
    no_cat = out["Category Path"].str.startswith("No Category", na=False).sum()

    print(f"\n{'='*50}")
    print(f"Found     : {found}")
    print(f"No Category: {no_cat}")
    print(f"Errors    : {errors}")
    print(f"Total     : {total}")
    print(f"{'='*50}")
    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
