# Daraz Product Category Scraper

A Python-based web scraper that extracts **complete category paths** from [Daraz](https://www.daraz.com.bd/) product pages. Built to handle dynamically-loaded JavaScript content using both Selenium and Playwright.

---

## Problem Statement

Daraz product pages load their breadcrumb navigation **dynamically via JavaScript**. The initial HTML response from the server contains an empty skeleton:

```html
<!-- What the server sends (requests only sees this) -->
<ul id="J_breadcrumb">

</ul>

<!-- What JavaScript renders (what users actually see) -->
<ul id="J_breadcrumb">
  <li><a title="Groceries">Groceries</a></li>
  <li><a title="Baking & Cooking">Baking & Cooking</a></li>
  <li><a title="Condiment Dressing">Condiment Dressing</a></li>
  <li><a title="BBQ Sauce">BBQ Sauce</a></li>
  <li><span class="breadcrumb_item_anchor_last">Product Name</span></li>
</ul>
```

**Standard HTTP libraries (requests, urllib) cannot execute JavaScript**, so they only capture the empty skeleton — resulting in incomplete or missing category data.

### The Challenge

| Approach | Result |
|---|---|
| `requests` + HTML parsing | ❌ Empty breadcrumb container (16 chars of whitespace) |
| `requests` + JSON-LD | ⚠️ Only 3 levels: `Groceries > Baking & Cooking > Condiment Dressing` |
| **Selenium / Playwright** | ✅ Full 4+ levels: `Groceries > Baking & Cooking > Condiment Dressing > BBQ Sauce` |

---

## Solution Architecture

This project provides **two browser-automation solutions** that render JavaScript and extract the complete breadcrumb:

### 1. Selenium Version (`daraz_selenium_scraper.py`)
- Uses **Selenium WebDriver** with headless Chrome
- Launches a real browser instance, renders JavaScript, waits for dynamic content
- Slower but widely compatible

### 2. Playwright Version (`daraz_playwright_scraper.py`) ⭐ Recommended
- Uses **Microsoft Playwright** with headless Chromium
- 2-3x faster than Selenium
- Reuses browser instances across multiple products (batch processing)
- More efficient DOM queries

---

## Project Structure

```
daraz-category-scraper/
├── README.md                          # This file
├── daraz_selenium_scraper.py          # Selenium-based scraper
├── daraz_playwright_scraper.py        # Playwright-based scraper (recommended)
├── input_ids.xlsx                     # Input: Product IDs (you create this)
└── output_categories.xlsx             # Output: Category paths (generated)
```

---

## Installation

### Prerequisites

- Python 3.8+
- Chrome/Chromium browser installed

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/daraz-category-scraper.git
cd daraz-category-scraper
```

### Step 2: Create Virtual Environment (Recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### Step 3: Install Dependencies

**For Selenium version:**
```bash
pip install selenium pandas openpyxl tqdm
```

**For Playwright version (recommended):**
```bash
pip install playwright pandas openpyxl
playwright install chromium
```

---

## Usage

### 1. Prepare Input File

Create an Excel file named `input_ids.xlsx` with a single column:

| Product ID |
|---|
| 572381417 |
| 554442035 |
| 564027774 |
| ... |

> **Note:** Product IDs should be stored as **text/string**, not numbers. Excel may auto-format them; right-click the column → Format Cells → Text.

### 2. Run the Scraper

**Selenium version:**
```bash
python daraz_selenium_scraper.py
```

**Playwright version (faster):**
```bash
python daraz_playwright_scraper.py
```

### 3. Check Output

The scraper generates `output_categories.xlsx` with three columns:

| Product ID | Product URL | Category Path |
|---|---|---|
| 572381417 | `https://www.daraz.com.bd/products/-i572381417.html` | `Groceries > Canned, Dry & Packaged Foods > Instant & Ready to Eat` |
| 554442035 | `https://www.daraz.com.bd/products/-i554442035.html` | `Groceries > Baking & Cooking > Condiment Dressing > BBQ Sauce` |
| 564027774 | `https://www.daraz.com.bd/products/-i564027774.html` | `Mother & Baby > Baby Personal Care > Skin Care` |

---

## Configuration

Edit the `CONFIG` section at the top of each script to customize behavior:

```python
# ======================
# CONFIG
# ======================

INPUT_FILE   = "input_ids.xlsx"      # Input Excel file
OUTPUT_FILE  = "output_categories.xlsx" # Output Excel file
MAX_WORKERS  = 3                      # Parallel workers (Selenium: 2, Playwright: 3)
DELAY_MIN    = 1.5                    # Minimum delay between requests (seconds)
DELAY_MAX    = 3.0                    # Maximum delay between requests (seconds)
TIMEOUT      = 30                     # Page load timeout (seconds)
RESUME       = True                   # Resume from previous run if output exists
DARAZ_DOMAIN = "daraz.com.bd"         # Daraz domain (change for other regions)
```

### Supported Daraz Domains

| Country | Domain |
|---|---|
| Bangladesh | `daraz.com.bd` |
| Pakistan | `daraz.pk` |
| Sri Lanka | `daraz.lk` |
| Nepal | `daraz.np` |
| Myanmar | `daraz.com.mm` |

---

## How It Works

### Extraction Logic

1. **Launch headless browser** (Chrome/Chromium)
2. **Navigate to product page**: `https://www.daraz.com.bd/products/-i{ID}.html`
3. **Wait for breadcrumb element** (`#J_breadcrumb`) to load
4. **Extract category names** from `<a title="...">` tags inside the breadcrumb
5. **Skip the last `<li>`** (product name, has no `<a>` tag)
6. **Join categories** with ` > ` separator
7. **Fallback to JSON-LD** if breadcrumb extraction fails

### HTML Structure Parsed

```html
<div data-spm="breadcrumb">
  <ul class="breadcrumb" id="J_breadcrumb">
    <li>
      <a title="Groceries" href="...">Groceries</a>
    </li>
    <li>
      <a title="Baking & Cooking" href="...">Baking & Cooking</a>
    </li>
    <li>
      <a title="Condiment Dressing" href="...">Condiment Dressing</a>
    </li>
    <li>
      <a title="BBQ Sauce" href="...">BBQ Sauce</a>        ← 4th category level
    </li>
    <li>
      <span class="breadcrumb_item_anchor_last">Product Name</span>  ← Skipped
    </li>
  </ul>
</div>
```

### Extraction Strategy Priority

| Priority | Method | Description |
|---|---|---|
| 1 | `#J_breadcrumb` `<a>` tags | Primary — extracts from `title` attribute |
| 2 | `ul.breadcrumb` `<a>` tags | Backup selector |
| 3 | `[data-spm="breadcrumb"]` | Alternative container |
| 4 | JSON-LD `Product.category` | Fallback — only 3 levels |

---

## Performance Comparison

| Metric | Selenium | Playwright |
|---|---|---|
| **Speed per product** | ~8-12 seconds | ~3-5 seconds |
| **100 products** | ~15-20 minutes | ~5-8 minutes |
| **Browser overhead** | High (new instance per product) | Low (batch reuse) |
| **Memory usage** | Higher | Lower |
| **Reliability** | Good | Better |
| **Setup complexity** | Requires ChromeDriver | Auto-managed by Playwright |

### Playwright Optimizations

- **Batch processing**: One browser instance handles 10 products before closing
- **Headless Chromium**: Lighter than full Chrome
- **Direct DOM queries**: Native Playwright selectors (faster than WebDriver)
- **Smart waiting**: `domcontentloaded` instead of `networkidle`

---

## Troubleshooting

### Issue: `No Category` or empty results

**Cause:** The breadcrumb container is empty in the initial HTML (JavaScript hasn't rendered it yet).

**Solution:**
- Increase `DELAY_MIN` and `DELAY_MAX` to give JavaScript more time
- Increase the `time.sleep(2)` in the extraction function to `3` or `4`
- Check if Daraz changed their HTML structure (inspect the page in browser)

### Issue: `Error: Timeout`

**Cause:** Page took too long to load or Daraz is blocking requests.

**Solution:**
- Increase `TIMEOUT` value
- Increase delays between requests (Daraz may rate-limit)
- Reduce `MAX_WORKERS` to 1
- Use a VPN or proxy if IP is blocked

### Issue: ChromeDriver not found

**Cause:** ChromeDriver is not in your system PATH.

**Solution:**
```bash
# Option 1: Use webdriver-manager (auto-downloads)
pip install webdriver-manager

# Then modify the script:
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

# Option 2: Manual download
# https://chromedriver.chromium.org/downloads
# Place chromedriver.exe in your project folder or add to PATH
```

### Issue: Playwright `chromium` not found

**Cause:** Playwright browsers not installed.

**Solution:**
```bash
playwright install chromium
```

---

## Development History

This project went through **7 iterations** to solve the dynamic content challenge:

| Version | Approach | Result |
|---|---|---|
| v1 | `requests` + HTML regex | ❌ Empty breadcrumb |
| v2 | `requests` + 10 HTML patterns | ❌ Still empty |
| v3 | `requests` + JSON-LD | ⚠️ Only 3 levels |
| v4 | `requests` + enhanced patterns | ❌ Empty container |
| v5 | `requests` + product name append | ❌ Wrong approach |
| v6 | `requests` + reordered patterns | ❌ 16-char container |
| **v7 Selenium** | **Browser automation** | ✅ **Full path working** |
| **v8 Playwright** | **Optimized browser automation** | ✅ **Fast + full path** |

### Key Insight

> The breadcrumb HTML container is **empty** (16 chars of whitespace) in the server response. JavaScript fetches category data via internal API and injects it into the DOM **after page load**. Only browser automation tools (Selenium/Playwright) that execute JavaScript can capture the complete breadcrumb.

---

## Legal & Ethical Notice

This tool is for **educational and research purposes only**. Before scraping:

- Review [Daraz's Terms of Service](https://www.daraz.com.bd/terms/)
- Respect `robots.txt` rules
- Do not overwhelm servers with excessive requests
- Use reasonable delays between requests
- Consider contacting Daraz for API access if you need bulk data

The authors are not responsible for misuse of this tool.

---

## License

MIT License — feel free to use, modify, and distribute with attribution.

---

## Contributing

Pull requests welcome! If you find a bug or want to add support for other e-commerce platforms:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request with clear description

---

## Author

Built with persistence to solve the dynamic content challenge.

---

## Acknowledgments

- [Selenium](https://www.selenium.dev/) — Browser automation
- [Playwright](https://playwright.dev/) — Fast, reliable browser automation
- [Pandas](https://pandas.pydata.org/) — Data manipulation
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) — HTML parsing (early attempts)
