"""
Database connection, models, and table initialization.
"""
import os
from datetime import date
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, Boolean, Text,
    MetaData, Table, inspect
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Neon uses postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── ORM Models ────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(50), unique=True, nullable=False, index=True)
    email         = Column(String(120), unique=True, nullable=False)
    hashed_pw     = Column(String(200), nullable=False)
    is_active     = Column(Boolean, default=True)
    must_change_pw = Column(Boolean, default=False)


class StockData(Base):
    __tablename__ = "stock_data"
    id                       = Column(Integer, primary_key=True, index=True)
    ticker                   = Column(String(10), nullable=False, index=True)
    company_name             = Column(String(100))
    industry                 = Column(String(80))
    earnings_date            = Column(String(30))
    earnings_soon            = Column(String(10))
    current_price            = Column(Float)
    data_date                = Column(Date, default=date.today, index=True)
    nf_expiry                = Column(String(12))
    nf_strike                = Column(Float)
    nf_call_price            = Column(Float)
    n2f_expiry               = Column(String(12))
    n2f_strike               = Column(Float)
    n2f_call_price           = Column(Float)
    nf_strike_diff           = Column(Float)
    n2f_strike_diff          = Column(Float)
    nf_signal                = Column(String(10))
    n2f_signal               = Column(String(10))
    notes                    = Column(Text)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables ready.")
