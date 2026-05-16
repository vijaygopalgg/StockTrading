# 📈 Smart Weekly Covered Call

A secure, cloud-hosted web application that analyzes the **top 500 stocks (S&P 500)**, correlates quarterly earnings results with near-term options premiums, and helps investors make educated decisions on **which covered call options to buy each week**.

---

## 🎯 What It Does

Covered call strategies generate income by selling call options against stocks you already own. The hard part is knowing *which* strike to sell and *when*. This app automates that research by:

- Pulling daily market data for all S&P 500 stocks after market close
- Correlating quarterly earnings results (EPS beats/misses) with options premium spikes
- Analyzing the next two weekly expiry cycles (Next Friday = NF, Friday after = N2F)
- Generating **Good / Bad signals** for each strike based on premium vs. downside risk
- Storing everything in a cloud PostgreSQL database for trend analysis over time

---

## 🖥️ Live Features

- **Secure Login** — Register, login, and change password
- **Options Dashboard** — Sortable, filterable table of all 500 stocks with signal columns
- **Signal Columns:**
  | Column | Description |
  |---|---|
  | NF Strike – Current Price | Distance to next Friday's strike |
  | N2F Strike – Current Price | Distance to the following Friday's strike |
  | NF Signal | Good ✅ / Bad ❌ for next Friday |
  | N2F Signal | Good ✅ / Bad ❌ for the week after |
- **Refresh Button** — Pulls latest data from Yahoo Finance on demand
- **Earnings Correlation** — Flags stocks with recent quarterly results that historically spike premiums

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python FastAPI |
| Database | PostgreSQL (Neon.tech cloud) |
| Frontend | HTML / JS (served by FastAPI) |
| Auth | JWT tokens with bcrypt password hashing |
| Data Source | Yahoo Finance (yfinance) |
| Hosting | Render.com |

---

## 🚀 Deployment

This app is deployed on **Render.com** with a **Neon.tech** cloud database — no local server needed.

### Prerequisites
- A [Neon.tech](https://neon.tech) account (free) — for PostgreSQL
- A [Render.com](https://render.com) account (free) — for hosting
- This GitHub repo connected to Render

### Environment Variables
Set these in your Render dashboard:

| Variable | Value |
|---|---|
| postgresql://neondb_owner:npg_0ibZI7crwSxE@ep-aged-mountain-aqvbjego.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require
| Your Neon connection string |
| `SECRET_KEY` | A long random secret string |

### Deploy Steps
1. Fork or clone this repo
2. Create a free PostgreSQL database at [neon.tech](https://neon.tech) and copy the connection string
3. Go to [render.com](https://render.com) → New Web Service → connect this repo
4. Set the environment variables above
5. Render auto-deploys on every push to `main`

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql://...
export SECRET_KEY=your-secret-key

# Run locally
python run.py
# App runs at http://localhost:8000
```

---

## 📁 Project Structure

```
smart_covered_call/
├── app/
│   ├── main.py          # FastAPI app entry point
│   ├── database.py      # PostgreSQL connection & schema
│   ├── routers/
│   │   ├── auth.py      # Login, register, change password
│   │   ├── users.py     # User management
│   │   └── stocks.py    # Options data & refresh logic
├── templates/
│   └── index.html       # Frontend (single-page app)
├── requirements.txt     # Python dependencies
├── render.yaml          # Render.com deployment config
└── run.py               # Local dev server
```

---

## 📊 How the Analysis Works

1. **Data Pull** — After market close, Yahoo Finance data is fetched for all S&P 500 tickers
2. **Options Chain** — Next two Friday expiries are identified; strike prices 1 step above current price are selected
3. **Signal Logic** — If `Strike > Current Price`, the position has upside room (Good ✅). If the stock has moved above the strike, the signal is Bad ❌
4. **Earnings Overlay** — Stocks with earnings in the past 2 weeks are flagged; elevated premiums post-earnings are highlighted as potential opportunities
5. **Storage** — All data is written to PostgreSQL for historical trend tracking

---

## 🔐 Security

- Passwords hashed with bcrypt
- JWT tokens with expiry for session management
- HTTPS enforced via Render's automatic SSL
- Database credentials stored as environment variables (never in code)

---

## 📌 Roadmap

- [ ] Email alerts for high-signal opportunities
- [ ] Portfolio tracker — log your actual covered call trades
- [ ] Historical backtesting of signals
- [ ] Earnings calendar integration
- [ ] Mobile-friendly responsive layout

---

## ⚠️ Disclaimer

This application is for **informational and educational purposes only**. It does not constitute financial advice. Always do your own research before making investment decisions.

---

## 📄 License

MIT License — free to use and modify for personal use.
