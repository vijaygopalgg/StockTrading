"""
Stocks router — serves options data and triggers live refresh from Yahoo Finance.
Logic ported directly from coveredCallLarge.py.
"""
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Optional

import yfinance as yf
from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db, StockData
from app.auth import get_current_user
from app.database import User

router = APIRouter()

# ── Ticker master list (from coveredCallLarge.py) ─────────────────────────────
MASTER_TICKERS = [
    "A","AAL","AAP","AAPL","ABBV","ABC","ABMD","ABNB","ABR","ABT","ACGL","ACN","ACV","ADBE",
    "ADI","ADM","ADP","ADSK","AEE","AEP","AES","AFL","AIG","AIZ","AJG","AKAM","ALB","ALGN",
    "ALK","ALL","ALLE","ALSN","AMAT","AMCR","AMD","AME","AMGN","AMP","AMT","AMZN","ANET",
    "ANSS","AON","AOS","APA","APD","APH","APLD","APO","APP","APTV","ARE","ARGX","ARM","ASML",
    "ATO","ATVI","AVB","AVGO","AVY","AWK","AXON","AXP","AZN","AZO","BA","BAC","BAH","BAX",
    "BBWI","BBY","BDX","BEN","BF-B","BIIB","BIO","BK","BKNG","BKR","BLK","BMY","BR","BRK-B",
    "BRO","BSX","BWA","BXP","C","CAG","CAH","CAKE","CARR","CAT","CAVA","CB","CBOE","CBRE",
    "CCEP","CCI","CCL","CDNS","CDW","CE","CEG","CELH","CF","CFG","CHD","CHRW","CHTR","CI",
    "CINF","CL","CLS","CLX","CMA","CMCSA","CME","CMG","CMI","CMS","CNC","CNP","COF","COIN",
    "COO","COP","COST","CPB","CPRT","CPT","CRL","CRM","CRS","CRWD","CSCO","CSGP","CSX","CTAS",
    "CTLT","CTRA","CTSH","CTVA","CUK","CVNA","CVS","CVX","CZR","D","DAL","DASH","DD","DDOG",
    "DE","DECK","DFS","DG","DGX","DHI","DHR","DIS","DISH","DKNG","DLR","DLTR","DOV","DOW",
    "DPZ","DRE","DRI","DTE","DUK","DVA","DVN","DXC","DXCM","EA","EBAY","ECL","ED","EFX","EIX",
    "EL","ELF","EME","EMN","EMR","ENPH","ENX","EOG","EPAM","EPD","EQIX","EQR","EQT","ES","ESS",
    "ETN","ETR","EVRG","EW","EXC","EXEL","EXPD","EXPE","EXR","F","FANG","FAST","FCNCA","FCX",
    "FDS","FDX","FE","FFIV","FI","FIG","FIS","FISV","FITB","FLT","FMC","FOX","FOXA","FRC",
    "FRO","FRSH","FRT","FTAI","FTNT","FTV","FUTU","GD","GE","GEHC","GEN","GFS","GILD","GIS",
    "GL","GLW","GM","GNRC","GOOG","GOOGL","GPC","GPN","GRAL","GRMN","GS","GWW","HAL","HAS",
    "HBAN","HCA","HD","HES","HIG","HII","HLT","HOLX","HON","HOOD","HPE","HPQ","HRL","HSIC",
    "HST","HSY","HTGC","HUM","HWM","IBKR","IBM","ICE","IDXX","IEX","IFF","ILMN","INCY","INSW",
    "INTC","INTU","INVH","IP","IPG","IQV","IR","IRM","ISRG","IT","ITW","IVZ","J","JBHT","JCI",
    "JEPI","JEPQ","JKHY","JNJ","JNPR","JPM","K","KDP","KEY","KEYS","KGC","KHC","KIM","KLAC",
    "KMB","KMI","KMX","KNSL","KO","KR","L","LBRT","LDOS","LEN","LH","LHX","LI","LIN","LKQ",
    "LLY","LMT","LNC","LNT","LOW","LRCX","LULU","LUV","LVS","LW","LYB","LYV","MA","MAA","MAR",
    "MARA","MAS","MCD","MCHP","MCK","MCO","MDLZ","MDT","MELI","MET","META","MGM","MHK","MKC",
    "MKTX","MLM","MMC","MMM","MNST","MO","MOD","MOH","MOS","MPC","MPWR","MRK","MRNA","MRO",
    "MRVL","MS","MSCI","MSFT","MSI","MSTR","MTB","MTD","MU","NCLH","NDAQ","NE","NEE","NEM",
    "NFLX","NGD","NI","NKE","NOC","NOV","NOW","NRG","NSC","NTAP","NTRS","NUE","NVDA","NVO",
    "NVR","NWL","NWS","NWSA","NXPI","O","ODFL","OGN","OKE","OMC","ON","ONON","ORCL","ORLY",
    "OXY","PANW","PAYC","PAYX","PCAR","PCG","PDD","PEAK","PEG","PEP","PERI","PFE","PFG","PG",
    "PGR","PH","PHM","PKG","PKI","PLD","PLTR","PM","PNC","PNR","PNW","POOL","PPG","PPL","PRU",
    "PSA","PSX","PTC","PWR","PXD","PYPL","QCOM","QLYS","QRVO","RCL","RDDT","RE","REG","REGN",
    "RELY","RF","RHI","RIOT","RJF","RL","RMBS","RMD","ROK","ROL","ROP","ROST","RSG","RTX",
    "SBAC","SBUX","SCHW","SEE","SHOP","SHW","SJM","SLB","SNA","SNPS","SO","SOFI","SPG","SPGI",
    "SPOT","SRE","STE","STT","STX","STZ","SWK","SWKS","SYF","SYK","SYY","T","TAP","TDG","TDW",
    "TDY","TEAM","TECH","TEL","TER","TEVA","TEX","TFC","TFX","TGT","TJX","TLRY","TMO","TMUS",
    "TPR","TRMB","TROW","TRV","TS","TSCO","TSLA","TSN","TT","TTD","TTWO","TXN","TXT","TYL",
    "UAL","UDR","UHS","ULTA","UNH","UNP","UPS","URI","USB","V","VFC","VLO","VMC","VNO","VRSK",
    "VRSN","VRT","VRTX","VTR","VTRS","VZ","WAB","WAT","WBA","WBD","WDAY","WDC","WEC","WELL",
    "WFC","WHD","WHR","WM","WMB","WMT","WRB","WRK","WST","WTW","WY","WYNN","XEL","XOM","XRAY",
    "XYL","YUM","ZBH","ZBRA","ZION","ZS","ZTS","ZWS",
]

# Track refresh status globally
refresh_status = {"running": False, "progress": 0, "total": 0, "message": "Idle"}


# ── Date helpers ──────────────────────────────────────────────────────────────

def next_friday(from_date=None):
    d = from_date or date.today()
    days_ahead = (4 - d.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return d + timedelta(days=days_ahead)


def get_expiry_dates():
    f1 = next_friday()
    f2 = next_friday(f1 + timedelta(days=1))
    return str(f1), str(f2)


# ── Options fetch (ported from coveredCallLarge.py) ───────────────────────────

def _is_rate_limit(e):
    msg = str(e).lower()
    return "too many" in msg or "rate limit" in msg or "429" in msg


def get_itm_call(ticker_obj, expiry, current_price):
    try:
        chain = ticker_obj.option_chain(expiry)
        calls = chain.calls[chain.calls["strike"] > current_price].sort_values("strike")
        if calls.empty:
            return None, None
        row    = calls.iloc[0]
        strike = float(row["strike"])
        bid    = float(row["bid"])       if row["bid"]       > 0 else None
        ask    = float(row["ask"])       if row["ask"]       > 0 else None
        last   = float(row["lastPrice"]) if row["lastPrice"] > 0 else None
        if bid and ask:
            mid = round((bid + ask) / 2, 2)
        elif last:
            mid = round(last, 2)
        else:
            mid = None
        return strike, mid
    except Exception:
        return None, None


def process_ticker(ticker, expiry1, expiry2):
    time.sleep(random.uniform(0.1, 0.5))
    row = {
        "ticker": ticker, "company_name": None, "industry": None,
        "earnings_date": None, "earnings_soon": None,
        "current_price": None, "data_date": date.today(),
        "nf_expiry": expiry1, "nf_strike": None, "nf_call_price": None,
        "n2f_expiry": expiry2, "n2f_strike": None, "n2f_call_price": None,
        "nf_strike_diff": None, "n2f_strike_diff": None,
        "nf_signal": None, "n2f_signal": None, "notes": "",
    }
    try:
        t    = yf.Ticker(ticker)
        info = t.info or {}

        row["company_name"] = info.get("shortName") or info.get("longName", ticker)
        row["industry"]     = info.get("industryDisp") or info.get("industry", "")
        price               = info.get("currentPrice") or info.get("regularMarketPrice")

        if not price:
            hist  = t.history(period="1d")
            price = float(hist["Close"].iloc[-1]) if not hist.empty else None

        if not price:
            row["notes"] = "No price data"
            return row

        row["current_price"] = round(price, 2)

        # Earnings
        try:
            cal = t.calendar
            if cal is not None and not cal.empty:
                ed = cal.columns[0] if hasattr(cal, "columns") else None
                if ed:
                    row["earnings_date"] = str(ed)
                    delta = (pd.to_datetime(ed).date() - date.today()).days if ed else 999
                    row["earnings_soon"] = "⚠️ Yes" if 0 <= delta <= 14 else "No"
        except Exception:
            pass

        avail = t.options
        if not avail:
            row["notes"] = "No options data"
            return row

        # NF
        if expiry1 in avail:
            s, p = get_itm_call(t, expiry1, price)
            row["nf_strike"] = s
            row["nf_call_price"] = p
            if s:
                diff = round(s - price, 2)
                row["nf_strike_diff"] = diff
                row["nf_signal"] = "Good" if diff > 0 else "Bad"

        # N2F
        if expiry2 in avail:
            s, p = get_itm_call(t, expiry2, price)
            row["n2f_strike"] = s
            row["n2f_call_price"] = p
            if s:
                diff = round(s - price, 2)
                row["n2f_strike_diff"] = diff
                row["n2f_signal"] = "Good" if diff > 0 else "Bad"

    except Exception as e:
        row["notes"] = str(e)[:120]

    return row


def run_refresh(db_url: str):
    """Background job: fetch all tickers and upsert into DB."""
    global refresh_status
    refresh_status = {"running": True, "progress": 0, "total": len(MASTER_TICKERS), "message": "Starting…"}

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import StockData
    import pandas as pd

    url = db_url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    eng = create_engine(url, pool_pre_ping=True)
    Sess = sessionmaker(bind=eng)

    expiry1, expiry2 = get_expiry_dates()
    today = date.today()
    done  = 0

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(process_ticker, t, expiry1, expiry2): t for t in MASTER_TICKERS}
        for future in as_completed(futures):
            row = future.result()
            done += 1
            refresh_status["progress"] = done
            refresh_status["message"]  = f"Processed {done}/{len(MASTER_TICKERS)}: {row['ticker']}"

            session = Sess()
            try:
                existing = session.query(StockData).filter(
                    StockData.ticker == row["ticker"],
                    StockData.data_date == today
                ).first()
                if existing:
                    for k, v in row.items():
                        setattr(existing, k, v)
                else:
                    session.add(StockData(**row))
                session.commit()
            except Exception as e:
                session.rollback()
            finally:
                session.close()

    refresh_status = {"running": False, "progress": done, "total": done, "message": "Complete ✅"}


# ── API Endpoints ─────────────────────────────────────────────────────────────

@router.get("/data")
def get_stock_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search: Optional[str] = Query(None),
    earnings_soon: Optional[bool] = Query(None),
    nf_signal: Optional[str] = Query(None),
    n2f_signal: Optional[str] = Query(None),
    sort_by: str = Query("current_price"),
    sort_dir: str = Query("desc"),
    limit: int = Query(500),
    offset: int = Query(0),
):
    today = date.today()
    q = db.query(StockData).filter(StockData.data_date == today)

    if search:
        s = f"%{search.upper()}%"
        q = q.filter(
            (StockData.ticker.ilike(s)) | (StockData.company_name.ilike(s))
        )
    if earnings_soon is True:
        q = q.filter(StockData.earnings_soon == "⚠️ Yes")
    if nf_signal:
        q = q.filter(StockData.nf_signal == nf_signal)
    if n2f_signal:
        q = q.filter(StockData.n2f_signal == n2f_signal)

    sort_col = getattr(StockData, sort_by, StockData.current_price)
    q = q.order_by(desc(sort_col) if sort_dir == "desc" else sort_col)

    total = q.count()
    rows  = q.offset(offset).limit(limit).all()

    return {
        "total": total,
        "date": str(today),
        "rows": [
            {
                "ticker":          r.ticker,
                "company_name":    r.company_name,
                "industry":        r.industry,
                "earnings_date":   r.earnings_date,
                "earnings_soon":   r.earnings_soon,
                "current_price":   r.current_price,
                "nf_expiry":       r.nf_expiry,
                "nf_strike":       r.nf_strike,
                "nf_call_price":   r.nf_call_price,
                "n2f_expiry":      r.n2f_expiry,
                "n2f_strike":      r.n2f_strike,
                "n2f_call_price":  r.n2f_call_price,
                "nf_strike_diff":  r.nf_strike_diff,
                "n2f_strike_diff": r.n2f_strike_diff,
                "nf_signal":       r.nf_signal,
                "n2f_signal":      r.n2f_signal,
                "notes":           r.notes,
            }
            for r in rows
        ],
    }


@router.post("/refresh")
def trigger_refresh(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    global refresh_status
    if refresh_status["running"]:
        raise HTTPException(409, "Refresh already in progress")
    import os
    db_url = os.environ.get("DATABASE_URL", "")
    background_tasks.add_task(run_refresh, db_url)
    return {"message": "Refresh started"}


@router.get("/refresh/status")
def get_refresh_status(current_user: User = Depends(get_current_user)):
    return refresh_status


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    rows = db.query(StockData).filter(StockData.data_date == today).all()
    total         = len(rows)
    good_nf       = sum(1 for r in rows if r.nf_signal  == "Good")
    bad_nf        = sum(1 for r in rows if r.nf_signal  == "Bad")
    good_n2f      = sum(1 for r in rows if r.n2f_signal == "Good")
    bad_n2f       = sum(1 for r in rows if r.n2f_signal == "Bad")
    earnings_soon = sum(1 for r in rows if r.earnings_soon == "⚠️ Yes")
    return {
        "total": total, "good_nf": good_nf, "bad_nf": bad_nf,
        "good_n2f": good_n2f, "bad_n2f": bad_n2f,
        "earnings_soon": earnings_soon,
        "date": str(today),
    }
