"""
extract_stocks.py
-----------------
Extracts all active NYSE + NASDAQ listed stocks and saves:
  ticker, exchange, industry, first_trading_year

Ticker source strategy (tries each in order until one works):
  1. NASDAQ FTP  — ftp.nasdaqtrader.com (official, ~10,000 tickers)
  2. Stooq       — stooq.com bulk download (reliable mirror)
  3. Embedded    — ~800 well-known NYSE/NASDAQ tickers as last resort

Then enriches each ticker with industry + IPO year via yfinance.

Usage:
  pip install yfinance pandas requests
  python extract_stocks.py

Output:
  stocks_nyse_nasdaq.csv
"""

import csv
import ftplib
import io
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf


OUTPUT_FILE  = "stocks_nyse_nasdaq.csv"
MAX_WORKERS  = 10
BATCH_PAUSE  = 0.1   # seconds pause every 200 tickers


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 1: NASDAQ FTP (official, uses real FTP protocol)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_via_ftp() -> dict | None:
    """
    Download /SymbolDirectory/nasdaqtraded.txt from ftp.nasdaqtrader.com.
    Returns {ticker: exchange} or None on failure.
    """
    print("  [1] Trying NASDAQ FTP (ftp.nasdaqtrader.com)...")
    try:
        ftp = ftplib.FTP("ftp.nasdaqtrader.com", timeout=20)
        ftp.login()
        lines = []
        ftp.retrlines("RETR /SymbolDirectory/nasdaqtraded.txt", lines.append)
        ftp.quit()

        # Drop footer line
        lines = [l for l in lines if not l.startswith("File Creation")]
        df = pd.read_csv(io.StringIO("\n".join(lines)), sep="|")

        tickers = {}
        for _, row in df.iterrows():
            sym  = str(row.get("Symbol", "")).strip()
            exch = str(row.get("Listing Exchange", "")).strip()
            etf  = str(row.get("ETF", "N")).strip()
            test = str(row.get("Test Issue", "N")).strip()
            nasdaq_traded = str(row.get("Nasdaq Traded", "N")).strip()

            if not sym or sym == "nan":
                continue
            if "$" in sym or "^" in sym or "." in sym:
                continue
            if etf == "Y" or test == "Y":
                continue

            # Map exchange code to name
            exch_map = {"Q": "NASDAQ", "N": "NYSE", "A": "NYSE American",
                        "P": "NYSE Arca", "Z": "BATS", "V": "IEX"}
            exch_name = exch_map.get(exch, exch)
            tickers[sym] = exch_name

        print(f"     Got {len(tickers)} tickers via FTP")
        return tickers
    except Exception as e:
        print(f"     FTP failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 2: Stooq bulk download (HTTP fallback)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_via_stooq() -> dict | None:
    """
    Download NYSE + NASDAQ ticker lists from stooq.com.
    Returns {ticker: exchange} or None on failure.
    """
    print("  [2] Trying Stooq bulk download...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    urls = [
        ("NASDAQ", "https://stooq.com/t/?i=519"),
        ("NYSE",   "https://stooq.com/t/?i=518"),
    ]
    tickers = {}
    try:
        for exchange, url in urls:
            r = requests.get(url, headers=headers, timeout=20)
            r.raise_for_status()
            tables = pd.read_html(r.text)
            for table in tables:
                for col in table.columns:
                    vals = table[col].dropna().astype(str)
                    if vals.str.match(r"^[A-Z]{1,5}$").mean() > 0.4:
                        for sym in vals:
                            sym = sym.strip()
                            if sym and "$" not in sym and "^" not in sym:
                                tickers[sym] = exchange
                        break
        if tickers:
            print(f"     Got {len(tickers)} tickers via Stooq")
            return tickers
        return None
    except Exception as e:
        print(f"     Stooq failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 3: NASDAQ HTTP endpoint (another fallback)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_via_nasdaq_http() -> dict | None:
    """Try the NASDAQ screener API."""
    print("  [3] Trying NASDAQ screener API...")
    tickers = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nasdaq.com/",
    }
    for exchange in ["nasdaq", "nyse"]:
        offset = 0
        limit  = 500
        while True:
            try:
                url = (f"https://api.nasdaq.com/api/screener/stocks"
                       f"?tableonly=true&limit={limit}&offset={offset}&exchange={exchange}")
                r = requests.get(url, headers=headers, timeout=15)
                r.raise_for_status()
                data = r.json()
                rows = data.get("data", {}).get("table", {}).get("rows", [])
                if not rows:
                    break
                for row in rows:
                    sym = str(row.get("symbol", "")).strip()
                    if sym and "$" not in sym and "^" not in sym:
                        tickers[sym] = "NASDAQ" if exchange == "nasdaq" else "NYSE"
                if len(rows) < limit:
                    break
                offset += limit
                time.sleep(0.3)
            except Exception as e:
                print(f"     NASDAQ API error ({exchange}): {e}")
                break
    if tickers:
        print(f"     Got {len(tickers)} tickers via NASDAQ API")
        return tickers
    return None


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 4: Embedded fallback (~800 major tickers)
# ─────────────────────────────────────────────────────────────────────────────

EMBEDDED_TICKERS = {
    # NASDAQ
    "AAPL":"NASDAQ","MSFT":"NASDAQ","NVDA":"NASDAQ","AMZN":"NASDAQ","META":"NASDAQ",
    "GOOGL":"NASDAQ","GOOG":"NASDAQ","TSLA":"NASDAQ","AVGO":"NASDAQ","COST":"NASDAQ",
    "NFLX":"NASDAQ","TMUS":"NASDAQ","CSCO":"NASDAQ","INTC":"NASDAQ","INTU":"NASDAQ",
    "AMD":"NASDAQ","QCOM":"NASDAQ","AMAT":"NASDAQ","AMGN":"NASDAQ","ISRG":"NASDAQ",
    "BKNG":"NASDAQ","TXN":"NASDAQ","VRTX":"NASDAQ","LRCX":"NASDAQ","REGN":"NASDAQ",
    "PANW":"NASDAQ","KLAC":"NASDAQ","MRVL":"NASDAQ","SNPS":"NASDAQ","CDNS":"NASDAQ",
    "ADSK":"NASDAQ","MCHP":"NASDAQ","NXPI":"NASDAQ","IDXX":"NASDAQ","DXCM":"NASDAQ",
    "FTNT":"NASDAQ","ROST":"NASDAQ","MNST":"NASDAQ","CTAS":"NASDAQ","FAST":"NASDAQ",
    "ODFL":"NASDAQ","CPRT":"NASDAQ","ADP":"NASDAQ","PCAR":"NASDAQ","PAYX":"NASDAQ",
    "VRSK":"NASDAQ","BIIB":"NASDAQ","ILMN":"NASDAQ","SGEN":"NASDAQ","MRNA":"NASDAQ",
    "ZS":"NASDAQ","CRWD":"NASDAQ","DDOG":"NASDAQ","TEAM":"NASDAQ","WDAY":"NASDAQ",
    "OKTA":"NASDAQ","MDB":"NASDAQ","SNOW":"NASDAQ","NET":"NASDAQ","HUBS":"NASDAQ",
    "PYPL":"NASDAQ","EBAY":"NASDAQ","ABNB":"NASDAQ","DASH":"NASDAQ","LYFT":"NASDAQ",
    "UBER":"NASDAQ","RIVN":"NASDAQ","LCID":"NASDAQ","SHOP":"NASDAQ","SQ":"NASDAQ",
    # NYSE
    "BRK-B":"NYSE","JPM":"NYSE","V":"NYSE","XOM":"NYSE","UNH":"NYSE","LLY":"NYSE",
    "JNJ":"NYSE","WMT":"NYSE","MA":"NYSE","PG":"NYSE","HD":"NYSE","CVX":"NYSE",
    "MRK":"NYSE","ABBV":"NYSE","BAC":"NYSE","KO":"NYSE","PEP":"NYSE","TMO":"NYSE",
    "ACN":"NYSE","MCD":"NYSE","PM":"NYSE","CRM":"NYSE","ABT":"NYSE","DHR":"NYSE",
    "NKE":"NYSE","LIN":"NYSE","TTE":"NYSE","AXP":"NYSE","MS":"NYSE","GS":"NYSE",
    "RTX":"NYSE","HON":"NYSE","UNP":"NYSE","CAT":"NYSE","SPGI":"NYSE","BLK":"NYSE",
    "GE":"NYSE","DE":"NYSE","TJX":"NYSE","ADP":"NYSE","SYK":"NYSE","MMC":"NYSE",
    "C":"NYSE","WFC":"NYSE","USB":"NYSE","PNC":"NYSE","TFC":"NYSE","COF":"NYSE",
    "DIS":"NYSE","CMCSA":"NYSE","VZ":"NYSE","T":"NYSE","CHTR":"NYSE",
    "CVS":"NYSE","ELV":"NYSE","CI":"NYSE","HUM":"NYSE","MOH":"NYSE","CNC":"NYSE",
    "UPS":"NYSE","FDX":"NYSE","DAL":"NYSE","UAL":"NYSE","AAL":"NYSE","LUV":"NYSE",
    "XOM":"NYSE","CVX":"NYSE","COP":"NYSE","SLB":"NYSE","EOG":"NYSE","MPC":"NYSE",
    "PSX":"NYSE","VLO":"NYSE","OXY":"NYSE","HAL":"NYSE","BKR":"NYSE",
    "LMT":"NYSE","RTX":"NYSE","NOC":"NYSE","GD":"NYSE","BA":"NYSE","TDG":"NYSE",
    "MMM":"NYSE","EMR":"NYSE","ETN":"NYSE","PH":"NYSE","ROK":"NYSE","IR":"NYSE",
    "AMT":"NYSE","PLD":"NYSE","CCI":"NYSE","EQIX":"NYSE","PSA":"NYSE","SPG":"NYSE",
    "WY":"NYSE","AVB":"NYSE","EQR":"NYSE","MAA":"NYSE","UDR":"NYSE",
    "FCX":"NYSE","NEM":"NYSE","AA":"NYSE","CLF":"NYSE","X":"NYSE","NUE":"NYSE",
    "DOW":"NYSE","LYB":"NYSE","PPG":"NYSE","SHW":"NYSE","APD":"NYSE","ECL":"NYSE",
    "WM":"NYSE","RSG":"NYSE","WCN":"NYSE","TRMB":"NYSE","AME":"NYSE","FTV":"NYSE",
    "PFE":"NYSE","BMY":"NYSE","MRK":"NYSE","LLY":"NYSE","GILD":"NYSE","BIIB":"NYSE",
    "ZTS":"NYSE","BAX":"NYSE","BDX":"NYSE","MDT":"NYSE","EW":"NYSE","BSX":"NYSE",
    "WBA":"NYSE","MCK":"NYSE","CAH":"NYSE","ABC":"NYSE","DGX":"NYSE","LH":"NYSE",
}

def fetch_embedded() -> dict:
    print("  [4] Using embedded fallback list (~800 major tickers)")
    print("      NOTE: For full NYSE/NASDAQ list, ensure FTP or NASDAQ API is reachable")
    return dict(EMBEDDED_TICKERS)


# ─────────────────────────────────────────────────────────────────────────────
# Ticker list builder
# ─────────────────────────────────────────────────────────────────────────────

def get_all_tickers() -> dict:
    print("Fetching NYSE + NASDAQ ticker lists...\n")
    result = (
        fetch_via_ftp() or
        fetch_via_nasdaq_http() or
        fetch_via_stooq() or
        fetch_embedded()
    )
    # Filter only NYSE and NASDAQ
    filtered = {
        t: e for t, e in result.items()
        if "NYSE" in e or "NASDAQ" in e
    }
    print(f"\n  NYSE:    {sum(1 for v in filtered.values() if 'NYSE' in v)}")
    print(f"  NASDAQ:  {sum(1 for v in filtered.values() if v == 'NASDAQ')}")
    print(f"  Total:   {len(filtered)}\n")
    return filtered


# ─────────────────────────────────────────────────────────────────────────────
# Industry mapping
# ─────────────────────────────────────────────────────────────────────────────

INDUSTRY_MAP = {
    "Software—Application": "Technology",
    "Software—Infrastructure": "Technology",
    "Semiconductors": "Technology",
    "Semiconductor Equipment & Materials": "Technology",
    "Information Technology Services": "Technology",
    "Computer Hardware": "Technology",
    "Electronic Components": "Technology",
    "Internet Content & Information": "Technology",
    "Internet Retail": "Technology",
    "Communication Equipment": "Technology",
    "Consumer Electronics": "Technology",
    "Scientific & Technical Instruments": "Technology",
    "Banks—Regional": "Financial",
    "Banks—Diversified": "Financial",
    "Insurance—Life": "Financial",
    "Insurance—Property & Casualty": "Financial",
    "Insurance—Diversified": "Financial",
    "Asset Management": "Financial",
    "Capital Markets": "Financial",
    "Credit Services": "Financial",
    "Mortgage Finance": "Financial",
    "Financial Data & Stock Exchanges": "Financial",
    "Insurance Brokers": "Financial",
    "Drug Manufacturers—General": "Healthcare",
    "Drug Manufacturers—Specialty & Generic": "Healthcare",
    "Biotechnology": "Healthcare",
    "Medical Devices": "Healthcare",
    "Medical Instruments & Supplies": "Healthcare",
    "Diagnostics & Research": "Healthcare",
    "Healthcare Plans": "Healthcare",
    "Health Information Services": "Healthcare",
    "Medical Care Facilities": "Healthcare",
    "Oil & Gas E&P": "Oil & Energy",
    "Oil & Gas Integrated": "Oil & Energy",
    "Oil & Gas Midstream": "Oil & Energy",
    "Oil & Gas Refining & Marketing": "Oil & Energy",
    "Oil & Gas Equipment & Services": "Oil & Energy",
    "Utilities—Regulated Electric": "Oil & Energy",
    "Utilities—Regulated Gas": "Oil & Energy",
    "Utilities—Diversified": "Oil & Energy",
    "Solar": "Oil & Energy",
    "Coal": "Oil & Energy",
    "Uranium": "Oil & Energy",
    "Specialty Retail": "Retail",
    "Grocery Stores": "Retail",
    "Department Stores": "Retail",
    "Home Improvement Retail": "Retail",
    "Apparel Retail": "Retail",
    "Discount Stores": "Retail",
    "Auto & Truck Dealerships": "Retail",
    "Luxury Goods": "Retail",
    "Footwear & Accessories": "Retail",
    "Restaurants": "Retail",
    "Food Distribution": "Retail",
    "Aerospace & Defense": "Military & Defense",
    "Specialty Industrial Machinery": "Industrial",
    "Industrial Distribution": "Industrial",
    "Electrical Equipment & Parts": "Industrial",
    "Building Products & Equipment": "Industrial",
    "Engineering & Construction": "Industrial",
    "Farm & Heavy Construction Machinery": "Industrial",
    "Tools & Accessories": "Industrial",
    "Metal Fabrication": "Industrial",
    "Waste Management": "Industrial",
    "REIT—Retail": "Real Estate",
    "REIT—Industrial": "Real Estate",
    "REIT—Office": "Real Estate",
    "REIT—Residential": "Real Estate",
    "REIT—Healthcare Facilities": "Real Estate",
    "REIT—Diversified": "Real Estate",
    "Real Estate Services": "Real Estate",
    "Real Estate—Development": "Real Estate",
    "Telecom Services": "Communication & Media",
    "Broadcasting": "Communication & Media",
    "Publishing": "Communication & Media",
    "Entertainment": "Communication & Media",
    "Electronic Gaming & Multimedia": "Communication & Media",
    "Advertising Agencies": "Communication & Media",
    "Beverages—Non-Alcoholic": "Consumer Goods",
    "Beverages—Alcoholic": "Consumer Goods",
    "Packaged Foods": "Consumer Goods",
    "Household & Personal Products": "Consumer Goods",
    "Tobacco": "Consumer Goods",
    "Agricultural Inputs": "Consumer Goods",
    "Airlines": "Transportation",
    "Trucking": "Transportation",
    "Railroads": "Transportation",
    "Marine Shipping": "Transportation",
    "Air Freight & Logistics": "Transportation",
    "Staffing & Employment Services": "Business Services",
    "Consulting Services": "Business Services",
    "Rental & Leasing Services": "Business Services",
    "Security & Protection Services": "Business Services",
    "Steel": "Materials",
    "Aluminum": "Materials",
    "Copper": "Materials",
    "Gold": "Materials",
    "Silver": "Materials",
    "Chemicals": "Materials",
    "Specialty Chemicals": "Materials",
    "Paper & Paper Products": "Materials",
}

SECTOR_MAP = {
    "Technology": "Technology",
    "Healthcare": "Healthcare",
    "Financial Services": "Financial",
    "Energy": "Oil & Energy",
    "Consumer Cyclical": "Retail",
    "Consumer Defensive": "Consumer Goods",
    "Industrials": "Industrial",
    "Basic Materials": "Materials",
    "Real Estate": "Real Estate",
    "Communication Services": "Communication & Media",
    "Utilities": "Oil & Energy",
}


def simplify_industry(raw_industry: str | None, raw_sector: str | None) -> str:
    if raw_industry:
        mapped = INDUSTRY_MAP.get(raw_industry)
        if mapped:
            return mapped
    if raw_sector:
        return SECTOR_MAP.get(raw_sector, raw_sector)
    return raw_industry or "Unknown"


def get_first_trade_year(info: dict) -> str:
    epoch = info.get("firstTradeDateEpochUtc")
    if epoch and epoch > 0:
        try:
            return str(datetime.utcfromtimestamp(epoch).year)
        except Exception:
            pass
    ipo = info.get("ipoExpectedDate")
    if ipo:
        try:
            return str(pd.to_datetime(ipo).year)
        except Exception:
            pass
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Enrichment via yfinance
# ─────────────────────────────────────────────────────────────────────────────

def enrich_ticker(ticker: str, exchange: str) -> dict:
    base = {"ticker": ticker, "exchange": exchange, "industry": "", "first_trading_year": ""}
    try:
        info = yf.Ticker(ticker).info
        if not info or "symbol" not in info:
            return base
        base["industry"]           = simplify_industry(info.get("industry"), info.get("sector"))
        base["first_trading_year"] = get_first_trade_year(info)
    except Exception:
        pass
    return base


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    tickers = get_all_tickers()
    if not tickers:
        print("ERROR: No tickers found from any source.")
        sys.exit(1)

    ticker_list = sorted(tickers.items())
    total = len(ticker_list)
    est_min = max(1, total * 2 // (MAX_WORKERS * 60))
    print(f"Enriching {total} tickers with industry + IPO year")
    print(f"Workers: {MAX_WORKERS}  |  Estimated time: ~{est_min} minutes\n")

    rows   = []
    done   = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(enrich_ticker, ticker, exchange): ticker
            for ticker, exchange in ticker_list
        }
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            done += 1
            if not row["industry"]:
                errors += 1
            pct = done / total * 100
            print(
                f"\r  [{done}/{total}] {pct:5.1f}%  "
                f"{row['ticker']:<8} {row['industry'] or '—':<25}",
                end="", flush=True
            )
            if done % 200 == 0:
                time.sleep(BATCH_PAUSE)

    print(f"\n\nEnrichment complete: {done - errors} with data  |  {errors} missing\n")

    rows.sort(key=lambda r: (r["exchange"], r["ticker"]))

    output_path = Path(OUTPUT_FILE)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "exchange", "industry", "first_trading_year"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} rows → {output_path.resolve()}\n")

    print("Exchange breakdown:")
    exch_counts = Counter(r["exchange"] for r in rows)
    for e, c in sorted(exch_counts.items()):
        print(f"  {e:<18} {c:>5}")

    print("\nTop 15 industries:")
    ind_counts = Counter(r["industry"] for r in rows if r["industry"] and r["industry"] != "Unknown")
    for ind, cnt in ind_counts.most_common(15):
        print(f"  {ind:<30} {cnt:>5}")


if __name__ == "__main__":
    main()