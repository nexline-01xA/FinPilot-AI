import sqlite3,os
SCHEMA_PATH=os.path.join(os.path.dirname(__file__),'schema.sql')
def connect(db_path:str)->sqlite3.Connection:
    conn=sqlite3.connect(db_path); conn.row_factory=sqlite3.Row; conn.execute('PRAGMA foreign_keys = ON;'); return conn
def init_db(db_path:str,fresh:bool=False)->sqlite3.Connection:
    if fresh and os.path.exists(db_path): os.remove(db_path)
    conn=connect(db_path)
    with open(SCHEMA_PATH) as f: conn.executescript(f.read())
    conn.commit(); return conn
