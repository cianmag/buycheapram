# BuyCheapRAM

Compare cheap RAM deals by price per GB. DDR5, DDR4, laptop, server, and ECC memory ranked by value.

## Live Site

[buycheapram.com](https://buycheapram.com)

## What It Does

- Aggregates RAM prices from Newegg (and more retailers coming)
- Ranks by price per GB so you find the best deals
- Filter by DDR type, capacity, speed, form factor, ECC, latency
- Mobile-friendly, fast, no login required

## Tech Stack

- Static HTML/CSS/JS (no frameworks, no build step)
- JSON data file updated by scraper
- Hosted on Vercel

## Local Development

```bash
cd site
python3 -m http.server 8080
# Open http://localhost:8080
```

## Updating Data

Run the scraper to fetch latest prices:

```bash
python3 scraper/newegg_scrape.py
```

## Legal

- [Privacy Policy](/privacy-policy)
- [Terms of Service](/terms-of-service)
- [Affiliate Disclosure](/affiliate-disclosure)
- [Disclaimer](/disclaimer)
