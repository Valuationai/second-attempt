"""
DiligenceAI — database.py
SQLite backend for user accounts, saved analyses, and shared reports.
Works on Streamlit Cloud (SQLite is available by default).
"""

import sqlite3, hashlib, json, uuid, os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diligenceai.db")


def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_pro        INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS analyses (
                id           TEXT PRIMARY KEY,
                user_id      TEXT NOT NULL,
                company_name TEXT NOT NULL DEFAULT 'Unknown Company',
                period       TEXT NOT NULL DEFAULT '',
                health_score INTEGER NOT NULL DEFAULT 5,
                health_label TEXT NOT NULL DEFAULT 'Moderate',
                kpis_json    TEXT NOT NULL DEFAULT '{}',
                full_json    TEXT NOT NULL DEFAULT '{}',
                created_at   TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS shared_reports (
                share_id     TEXT PRIMARY KEY,
                user_id      TEXT NOT NULL,
                company_name TEXT NOT NULL DEFAULT 'Unknown Company',
                full_json    TEXT NOT NULL DEFAULT '{}',
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)


def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def _kpis_snap(data):
    k = data.get("kpis", {})
    return json.dumps({key: k.get(key, {}).get("value", "N/A")
        for key in ("revenue","net_profit","ebitda","gross_margin","net_margin",
                    "operating_cashflow","current_ratio","debt_to_equity","working_capital","total_debt")})


# ── AUTH ──────────────────────────────────────────────────────────────────────

def create_user(email, password, is_pro=False):
    uid = str(uuid.uuid4())
    try:
        with _conn() as c:
            c.execute("INSERT INTO users (id,email,password_hash,is_pro) VALUES (?,?,?,?)",
                      (uid, email.strip().lower(), _hash(password), int(is_pro)))
        return {"ok": True, "user_id": uid, "email": email.strip().lower(), "is_pro": is_pro}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "An account with that email already exists."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def login_user(email, password):
    with _conn() as c:
        row = c.execute("SELECT id,email,is_pro FROM users WHERE email=? AND password_hash=?",
                        (email.strip().lower(), _hash(password))).fetchone()
    if row:
        return {"ok": True, "user_id": row["id"], "email": row["email"], "is_pro": bool(row["is_pro"])}
    return {"ok": False, "error": "Invalid email or password."}


# ── ANALYSES ──────────────────────────────────────────────────────────────────

def save_analysis(user_id, data):
    aid = str(uuid.uuid4())
    with _conn() as c:
        c.execute("INSERT INTO analyses (id,user_id,company_name,period,health_score,health_label,kpis_json,full_json) VALUES (?,?,?,?,?,?,?,?)",
                  (aid, user_id, data.get("company_name","Unknown Company"), data.get("period",""),
                   data.get("health_score",5), data.get("health_label","Moderate"),
                   _kpis_snap(data), json.dumps(data)))
    return aid


def get_user_analyses(user_id):
    with _conn() as c:
        rows = c.execute("SELECT id,company_name,period,health_score,health_label,kpis_json,created_at "
                         "FROM analyses WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["kpis_json"] = json.loads(d["kpis_json"] or "{}")
        result.append(d)
    return result


def get_analysis(analysis_id, user_id):
    with _conn() as c:
        row = c.execute("SELECT full_json FROM analyses WHERE id=? AND user_id=?",
                        (analysis_id, user_id)).fetchone()
    return json.loads(row["full_json"]) if row else None


def delete_analysis(analysis_id, user_id):
    with _conn() as c:
        cur = c.execute("DELETE FROM analyses WHERE id=? AND user_id=?", (analysis_id, user_id))
    return cur.rowcount > 0


# ── SHARED REPORTS ────────────────────────────────────────────────────────────

def create_share_link(user_id, data):
    share_id = uuid.uuid4().hex[:8].upper()
    with _conn() as c:
        c.execute("INSERT INTO shared_reports (share_id,user_id,company_name,full_json) VALUES (?,?,?,?)",
                  (share_id, user_id, data.get("company_name","Unknown Company"), json.dumps(data)))
    return share_id


def get_shared_report(share_id):
    with _conn() as c:
        row = c.execute("SELECT full_json,company_name,created_at FROM shared_reports WHERE share_id=?",
                        (share_id.strip().upper(),)).fetchone()
    if row:
        return {"data": json.loads(row["full_json"]), "company_name": row["company_name"], "created_at": row["created_at"]}
    return None


init_db()
