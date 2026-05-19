# AW Client Report Portal

Portal for financial planning teams to manage client profiles, enter quarterly balances, auto-calculate SACS/TCC totals, and generate presentation-ready PDF reports.

Built per **AW Client Report Portal PRD v1.0** (Sagan AI Engineer Test).

## Features

- **Client profiles** — household info, Client 1/2, account structure, static SACS cashflow fields
- **Quarterly report entry** — pre-filled static data, balance entry with “use last value”, live calculations
- **Automated math** — PRD rules (excess, reserve target, retirement totals, grand total, liabilities separate)
- **PDF export** — SACS (2 pages) and TCC via ReportLab
- **Report history** — re-download prior quarterly reports

## Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, Flask |
| Database | SQLite (`RAILWAY_DATABASE_PATH` or `./data/portal.db`) |
| Frontend | HTML, CSS, JavaScript |
| PDF | ReportLab |
| Deploy | Railway (Gunicorn) |

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
python run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). A demo **Smith Family** client is seeded on first run.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RAILWAY_DATABASE_PATH` | SQLite file path (Railway volume) |
| `PORT` | HTTP port (Railway sets automatically) |
| `SECRET_KEY` | Flask session secret (production) |

## Railway Deploy

1. Create a Railway project and connect this repo.
2. Add a volume mounted at `/data` (optional but recommended).
3. Set `RAILWAY_DATABASE_PATH=/data/portal.db`.
4. Deploy — `Procfile` runs Gunicorn.

## Calculation Rules (PRD)

- **SACS excess** = Inflow − Outflow  
- **Private reserve target** = (6 × monthly expenses) + insurance deductibles  
- **TCC grand total** = C1 retirement + C2 retirement + non-retirement + trust  
- **Liabilities** are summed separately and **not** subtracted from net worth  
- **Trust** is **not** included in non-retirement total  

## Out of Scope (V1)

- Canva API export (PDF download covers core need)
- External API integrations (Schwab, RightCapital, Zillow, Pinnacle)
