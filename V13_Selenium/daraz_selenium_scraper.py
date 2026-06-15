"""
Daraz Product Category Scraper - SELENIUM VERSION
==================================================
Uses Selenium to render JavaScript and extract the FULL breadcrumb.
This gets the dynamically-loaded 4th category level.

Requirements:
  pip install selenium
  # Also need ChromeDriver: https://chromedriver.chromium.org/downloads
  # Or use webdriver-manager: pip install webdriver-manager
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

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("ERROR: Selenium not installed. Run: pip install selenium")
    exit(1)

# ======================
# CONFIG
# ======================

INPUT_FILE   = "input_ids.xlsx"
OUTPUT_FILE  = "output_categories.xlsx"
MAX_WORKERS  = 2        # Lower for Selenium (browser instances are heavy)
DELAY_MIN    = 2.0
DELAY_MAX    = 4.0
TIMEOUT      = 30
RESUME       = True

DARAZ_DOMAIN = "daraz.com.bd"


def create_driver():
    """Create a headless Chrome driver."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(TIMEOUT)
    return driver


def extract_category_selenium(driver, item_id):
    """
    Use Selenium to render the page and extract the FULL breadcrumb.
    """
    url = f"https://www.{DARAZ_DOMAIN}/products/-i{item_id}.html"

    try:
        driver.get(url)

        # Wait for breadcrumb to load
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "J_breadcrumb"))
            )
        except TimeoutException:
            pass

        # Additional wait for dynamic content
        time.sleep(3)

        # Method 1: Extract from breadcrumb <ul>
        try:
            breadcrumb = driver.find_element(By.ID, "J_breadcrumb")
            if breadcrumb:
                # Get all <a> tags (category links)
                links = breadcrumb.find_elements(By.TAG_NAME, "a")
                categories = []
                for link in links:
                    title = link.get_attribute("title")
                    if title:
                        text = html_module.unescape(title.strip())
                        if text and text.lower() not in ("home", "\u09b9\u09cb\u09ae", "daraz", ""):
                            categories.append(text)

                if len(categories) >= 2:
                    return " > ".join(categories)
        except Exception:
            pass

        # Method 2: Extract from any breadcrumb element
        try:
            breadcrumb = driver.find_element(By.CSS_SELECTOR, "[data-spm='breadcrumb']")
            if breadcrumb:
                links = breadcrumb.find_elements(By.TAG_NAME, "a")
                categories = []
                for link in links:
                    title = link.get_attribute("title")
                    if title:
                        text = html_module.unescape(title.strip())
                        if text and text.lower() not in ("home", "\u09b9\u09cb\u09ae", "daraz", ""):
                            categories.append(text)

                if len(categories) >= 2:
                    return " > ".join(categories)
        except Exception:
            pass

        # Method 3: Get page source and parse with regex
        page_source = driver.page_source

        # Try ul#J_breadcrumb
        m = re.search(r'<ul[^>]*id\s*=\s*["\']J_breadcrumb["\'][^>]*>(.*?)</ul>', page_source, re.DOTALL | re.IGNORECASE)
        if m:
            container = m.group(1)
            titles = []
            for mm in re.finditer(r'<a[^>]*title\s*=\s*["\']([^"\']+)["\'][^>]*>', container):
                title = mm.group(1).strip()
                title = html_module.unescape(title)
                if title and title.lower() not in ("home", "\u09b9\u09cb\u09ae", "daraz", ""):
                    titles.append(title)
            if len(titles) >= 2:
                return " > ".join(titles)

        # Method 4: JSON-LD fallback
        for m in re.finditer(r'<script[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>', page_source, re.DOTALL):
            try:
                data = json.loads(m.group(1).strip())
                for obj in (data if isinstance(data, list) else [data]):
                    if obj.get("@type") == "Product":
                        cat = obj.get("category")
                        if cat:
                            return cat.strip()
            except Exception:
                pass

        return None

    except Exception as e:
        return f"Error: {e}"


def process_row(item_id):
    """Process a single product."""
    driver = create_driver()
    try:
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        cat = extract_category_selenium(driver, item_id)
        url = f"https://www.{DARAZ_DOMAIN}/products/-i{item_id}.html"
        return item_id, url, cat or "No Category"
    finally:
        driver.quit()


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
    print(f"Processing {len(pending)} / {len(df)} rows...\n")

    new_results = {}

    for _, row in pending.iterrows():
        item_id = str(row["Product ID"]).strip()
        print(f"Processing {item_id}...")
        _, url, cat = process_row(item_id)
        new_results[item_id] = (url, cat)
        print(f"  Result: {cat}")

    # Rebuild output
    output_rows = []
    for _, row in df.iterrows():
        pid = str(row["Product ID"]).strip()
        if pid in new_results:
            url, cat = new_results[pid]
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
