"""
Smart Weekly Covered Call — FastAPI entry point
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import auth, users, stocks

app = FastAPI(title="Smart Weekly Covered Call", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()

app.include_router(auth.router,   prefix="/api/auth",   tags=["auth"])
app.include_router(users.router,  prefix="/api/users",  tags=["users"])
app.include_router(stocks.router, prefix="/api/stocks", tags=["stocks"])

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("templates/index.html") as f:
        return f.read()

@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(full_path: str):
    with open("templates/index.html") as f:
        return f.read()
