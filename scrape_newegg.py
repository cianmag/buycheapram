#!/usr/bin/env python3
"""
Scrape ALL RAM listings from Newegg — full catalog.
Auto-paginates until no more products found.
"""

import re
import json
import time
import hashlib
import subprocess
from datetime import datetime, timezone

# Category templates — will auto-paginate
CATEGORIES = [
    {
        "name": "Desktop Memory",
        "url_template": "https://www.newegg.com/Desktop-Memory/SubCategory/ID-147?Tid=16347&Page={page}",
        "start_page": 1,
    },
    {
        "name": "Laptop Memory",
        "url_template": "https://www.newegg.com/p/pl?N=100007609&PageSize=96&Page={page}",
        "start_page": 1,
    },
    {
        "name": "DDR4 Desktop (filtered)",
        "url_template": "https://www.newegg.com/p/pl?N=100007611%20600006050&PageSize=96&Page={page}",
        "start_page": 1,
    },
    {
        "name": "ECC/Server Memory",
        "url_template": "https://www.newegg.com/p/pl?N=100007616%20600006050&PageSize=96&Page={page}",
        "start_page": 1,
    },
]

MAX_EMPTY_PAGES = 2  # stop after this many consecutive empty pages
DELAY_BETWEEN_PAGES = 1.0

KNOWN_BRANDS = [
    "CORSAIR", "G.SKILL", "Crucial", "Kingston", "TeamGroup", "Team",
    "Patriot", "ADATA", "XPG", "V-COLOR", "Samsung", "SK Hynix", "Hynix",
    "Micron", "MSI", "ASUS", "GIGABYTE", "PNY", "Silicon Power", "NEMIX",
    "OWC", "Lexar", "HPE", "KLEVV", "Kingston FURY", "Timetec", "KINGBANK",
    "DATO", "Neo Forza", "Thermaltake", "OLOy", "GeIL", "ZADAK",
    "Mushkin", "Inland", "SKILL", "Patriot Memory", "Gloway", "KingSpec",
    "OWC", "SAMSUNG", "Netac", "Gloway", "HP", "Dell", "Lenovo",
]

BRAND_ALIASES = {
    "XPG": "ADATA",
    "Ballistix": "Crucial",
    "Hynix": "SK Hynix",
    "Team": "TeamGroup",
    "FURY": "Kingston FURY",
}

RAM_KEYWORDS = [
    "DDR", "RAM", "Memory", "UDIMM", "DIMM", "SO-DIMM", "SODIMM",
    "RDIMM", "ECC", "PC4", "PC5", "MHz",
]


def fetch_url(url, retries=2):
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                ["curl", "-sL", "--compressed", "-m", "25",
                 "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                 "-H", "Accept: text/html,application/xhtml+xml",
                 "-H", "Accept-Language: en-US,en;q=0.9",
                 url],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and len(result.stdout) > 1000:
                return result.stdout
        except Exception as e:
            print(f"  [WARN] Fetch attempt {attempt+1} failed: {e}")
        if attempt < retries:
            time.sleep(2)
    return None


def is_ram_product(title):
    title_lower = title.lower()
    has_keyword = any(kw.lower() in title_lower for kw in RAM_KEYWORDS)
    has_capacity = bool(re.search(r'\d+\s*GB', title, re.IGNORECASE))
    excludes = ["hair dryer", "printer", "monitor", "keyboard", "mouse",
                 "power supply", "nvme drive", "graphics card", "usb hub"]
    is_excluded = any(ex in title_lower for ex in excludes)
    return has_keyword and has_capacity and not is_excluded


def normalize_brand(title):
    title_upper = title.upper()
    for brand in KNOWN_BRANDS:
        if brand.upper() in title_upper:
            return BRAND_ALIASES.get(brand, brand).upper()
    first_word = title.split()[0] if title else "Unknown"
    return BRAND_ALIASES.get(first_word, first_word).upper()


def parse_ddr_type(title):
    t = title.upper()
    if "DDR5" in t: return "DDR5"
    if "DDR4" in t: return "DDR4"
    if "DDR3" in t: return "DDR3"
    if "DDR2" in t: return "DDR2"
    if "PC5-" in t or "PC5 " in t: return "DDR5"
    if "PC4-" in t or "PC4 " in t: return "DDR4"
    return "Unknown"


def parse_capacity(title):
    kit_total = re.search(r'(\d+)\s*GB\s*\(\s*\d+\s*x\s*\d+', title, re.IGNORECASE)
    if kit_total: return int(kit_total.group(1))
    kit_match = re.search(r'(\d+)\s*x\s*(\d+)\s*GB', title, re.IGNORECASE)
    if kit_match: return int(kit_match.group(1)) * int(kit_match.group(2))
    caps = re.findall(r'(\d+)\s*GB', title, re.IGNORECASE)
    if caps: return max(int(c) for c in caps)
    return 0


def parse_speed(title):
    mhz = re.search(r'(\d{3,5})\s*MHz', title, re.IGNORECASE)
    if mhz: return int(mhz.group(1))
    pc5 = re.search(r'PC5-(\d+)', title, re.IGNORECASE)
    if pc5: return int(pc5.group(1)) // 8
    pc4 = re.search(r'PC4-(\d+)', title, re.IGNORECASE)
    if pc4: return int(pc4.group(1)) // 8
    return 0


def parse_form_factor(title):
    t = title.upper()
    if "SO-DIMM" in t or "SODIMM" in t: return "SO-DIMM"
    if "RDIMM" in t: return "RDIMM"
    if "LAPTOP" in t: return "SO-DIMM"
    if "UDIMM" in t or "DIMM" in t: return "DIMM"
    return "DIMM"


def parse_ecc(title):
    t = title.lower()
    if "non-ecc" in t or "nonecc" in t: return False
    if "unbuffered" in t and "ecc" not in t: return False
    return "ecc" in t


def parse_cas_latency(title):
    cl = re.search(r'CL\s*(\d+)', title, re.IGNORECASE)
    return int(cl.group(1)) if cl else 0


def parse_kit_count(title):
    kit = re.search(r'\(\s*(\d+)\s*x\s*\d+\s*GB\s*\)', title, re.IGNORECASE)
    if kit: return int(kit.group(1))
    kit2 = re.search(r'(\d+)\s*x\s*\d+\s*GB', title, re.IGNORECASE)
    if kit2: return int(kit2.group(1))
    return 1


def parse_rgb(title):
    return "rgb" in title.lower()


def generate_asin(title, url):
    item_match = re.search(r'Item=(\w+)', url)
    if item_match: return "NEGG-" + item_match.group(1)
    return "NEGG-" + hashlib.md5(title.encode()).hexdigest()[:12].upper()


def parse_products_from_html(html):
    products = []
    containers = html.split('class="item-container')
    for container in containers[1:]:
        title_match = re.search(r'title="([^"]{15,400})"', container[:6000])
        if not title_match: continue
        title = title_match.group(1).strip()
        if not is_ram_product(title): continue

        url_match = re.search(r'href="(https://www\.newegg\.com/[^"]+)"', container[:6000])
        url = url_match.group(1) if url_match else "#"

        # Price: extract from price-current (HTML: $<strong>164</strong><sup>.99</sup>)
        price_match = re.search(r'price-current.*?\$\s*(?:<[^>]+>)*\s*(\d[\d,]*)\s*(?:<[^>]+>)*\s*\.(\d{2})', container, re.DOTALL)
        if not price_match:
            price_match = re.search(r'price-current.*?\$(\d[\d,]*\.?\d{0,2})', container, re.DOTALL)
        if not price_match: continue
        try:
            if price_match.lastindex and price_match.lastindex >= 2:
                price = float(price_match.group(1).replace(',', '') + '.' + price_match.group(2))
            else:
                price = float(price_match.group(1).replace(',', ''))
        except (ValueError, AttributeError): continue
        if price <= 0 or price > 50000: continue

        ddr_type = parse_ddr_type(title)
        capacity = parse_capacity(title)
        speed = parse_speed(title)
        price_per_gb = round(price / capacity, 2) if capacity > 0 else 0

        products.append({
            "title": title,
            "price": price,
            "capacity_gb": capacity,
            "speed_mhz": speed,
            "ddr_type": ddr_type,
            "form_factor": parse_form_factor(title),
            "ecc": parse_ecc(title),
            "cas_latency": parse_cas_latency(title),
            "brand": normalize_brand(title),
            "rgb": parse_rgb(title),
            "kit_count": parse_kit_count(title),
            "asin": generate_asin(title, url),
            "url": url,
            "price_per_gb": price_per_gb,
        })
    return products


def main():
    all_products = []
    seen_keys = set()
    total_pages = 0

    for cat in CATEGORIES:
        print(f"\n{'='*60}")
        print(f"Category: {cat['name']}")
        print(f"{'='*60}")
        consecutive_empty = 0
        page = cat["start_page"]

        while consecutive_empty < MAX_EMPTY_PAGES:
            url = cat["url_template"].format(page=page)
            print(f"  Page {page}...", end=" ", flush=True)
            html = fetch_url(url)

            if not html:
                print("FETCH FAIL")
                consecutive_empty += 1
                page += 1
                continue

            products = parse_products_from_html(html)
            new_count = 0
            for p in products:
                key = p["title"][:50].lower().strip()
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_products.append(p)
                    new_count += 1

            containers = html.count('class="item-container')
            print(f"{containers} containers, {len(products)} RAM, {new_count} new")

            if len(products) == 0 or new_count == 0:
                consecutive_empty += 1
            else:
                consecutive_empty = 0

            page += 1
            total_pages += 1
            time.sleep(DELAY_BETWEEN_PAGES)

    # Sort by price per GB
    all_products.sort(key=lambda p: p.get("price_per_gb", 9999))

    output = {
        "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "locale": "us",
        "source": "newegg.com",
        "count": len(all_products),
        "products": all_products,
    }

    out_path = "/home/cian/buycheapram/site/data/ram_prices.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*60}")
    print(f"DONE: {len(all_products)} unique RAM products from {total_pages} pages")
    print(f"Saved to {out_path}")
    print(f"{'='*60}")

    # Stats
    from collections import Counter
    ddr_counts = Counter(p["ddr_type"] for p in all_products)
    form_counts = Counter(p["form_factor"] for p in all_products)
    brands = len(set(p["brand"] for p in all_products))
    with_url = sum(1 for p in all_products if p["url"] and p["url"] != "#")
    ecc_count = sum(1 for p in all_products if p["ecc"])

    print(f"  DDR types: {dict(ddr_counts)}")
    print(f"  Form factors: {dict(form_counts)}")
    print(f"  ECC: {ecc_count}")
    print(f"  Unique brands: {brands}")
    print(f"  With working URLs: {with_url}/{len(all_products)}")
    if all_products:
        print(f"  Best $/GB: ${all_products[0]['price_per_gb']:.2f}/GB — {all_products[0]['title'][:60]}")


if __name__ == "__main__":
    main()
