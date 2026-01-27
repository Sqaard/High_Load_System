from fastapi import FastAPI, Query
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = FastAPI()

MASTER_DSN = os.getenv("MASTER_DSN")
REPLICA_DSN = os.getenv("REPLICA_DSN")

def get_conn(dsn):
    return psycopg2.connect(dsn, cursor_factory=RealDictCursor)

@app.on_event("startup")
def startup():
    # Create table if not exists (on master)
    with get_conn(MASTER_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS k6_test (
                    id SERIAL PRIMARY KEY,
                    payload INTEGER,
                    ts TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

from pydantic import BaseModel

class InsertReq(BaseModel):
    payload: int

class BoomReq(BaseModel):
    count: int = 1000000  # по умолчанию 1 млн записей

@app.post("/insert")
def insert(req: InsertReq):
    payload = req.payload
    with get_conn(MASTER_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO k6_test (payload) VALUES (%s) RETURNING id;", (payload,))
            result = cur.fetchone()
            conn.commit()
    return {"id": result['id']}

@app.post("/boom")
def boom(req: BoomReq):
    with get_conn(MASTER_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(f"INSERT INTO k6_test (payload) SELECT random()*1000 FROM generate_series(1, {req.count});")
            conn.commit()
    return {"status": "boom done", "inserted": req.count}

@app.get("/select")
def select(target: str = Query("master", enum=["master", "replica"])):
    dsn = MASTER_DSN if target == "master" else REPLICA_DSN
    with get_conn(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM k6_test;")
            result = cur.fetchone()
    return {"count": result['count'], "from": target}



@app.get("/health")
def health():
    return {"status": "ok"}