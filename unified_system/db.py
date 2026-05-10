# db.py — Kết nối PostgreSQL dùng chung
import os, psycopg2, psycopg2.extras, pandas as pd, streamlit as st
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

_DB = dict(host=os.getenv("DB_HOST","localhost"), port=int(os.getenv("DB_PORT",5432)),
           dbname=os.getenv("DB_NAME","kho_bai_giang"), user=os.getenv("DB_USER","postgres"),
           password=os.getenv("DB_PASS","123456"))

@st.cache_resource
def conn():
    return psycopg2.connect(**_DB, cursor_factory=psycopg2.extras.RealDictCursor)

def q(sql, p=None):
    try:
        c = conn()
        with c.cursor() as cur: 
            cur.execute(sql, p or ())
            return [dict(r) for r in cur.fetchall()]
    except Exception:
        conn.clear()
        c = conn()
        with c.cursor() as cur: 
            cur.execute(sql, p or ())
            return [dict(r) for r in cur.fetchall()]

def execute(sql, p=None):
    try:
        c = conn()
        with c.cursor() as cur: 
            cur.execute(sql, p or ())
        c.commit()
    except Exception:
        conn.clear()
        c = conn()
        with c.cursor() as cur: 
            cur.execute(sql, p or ())
        c.commit()

def q1(sql, p=None): rows=q(sql,p); return rows[0] if rows else {}
def df(sql, p=None): return pd.DataFrame(q(sql,p))
