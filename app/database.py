import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Kita pakai domain Pooler (aws-0-...) agar dapat jalur IPv4.
# 2. Kita pakai username lengkap (postgres.opmmcdsffhesnlolkcfa) agar tidak kena error Tenant Not Found.
# 3. Kita HAPUS "?pgbouncer=true" karena library psycopg2 di Python ternyata menolak parameter itu (invalid dsn).

DATABASE_URL = "postgresql://postgres.opmmcdsffhesnlolkcfa:dugoat061105@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres"

# Konfigurasi engine dengan pool_pre_ping agar stabil di jaringan cloud/hotspot
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()