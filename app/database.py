import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from flask import Flask, g


def init_db(app: Flask):
    Path(app.config["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)

    @app.before_request
    def open_db():
        g.db = sqlite3.connect(app.config["DATABASE_PATH"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    @app.teardown_request
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with app.app_context():
        _migrate(get_db(app))


def get_db(app: Flask | None = None):
    if app is not None:
        conn = sqlite3.connect(app.config["DATABASE_PATH"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    return g.db


@contextmanager
def db_cursor(conn=None):
    db = conn if conn is not None else g.db
    cur = db.cursor()
    try:
        yield cur
        db.commit()
    except Exception:
        db.rollback()
        raise


def _migrate(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            is_married INTEGER NOT NULL DEFAULT 0,
            monthly_inflow REAL NOT NULL DEFAULT 0,
            monthly_outflow REAL NOT NULL DEFAULT 0,
            insurance_deductibles REAL NOT NULL DEFAULT 0,
            schwab_label TEXT DEFAULT 'Schwab Investment Account',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            full_name TEXT NOT NULL,
            date_of_birth TEXT NOT NULL,
            ssn_last_four TEXT NOT NULL,
            UNIQUE(client_id, role)
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            category TEXT NOT NULL,
            account_type TEXT NOT NULL,
            label TEXT NOT NULL,
            account_last_four TEXT DEFAULT '',
            interest_rate REAL,
            property_address TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            quarter_label TEXT NOT NULL,
            report_date TEXT NOT NULL,
            balances_json TEXT NOT NULL DEFAULT '{}',
            calculations_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    _seed_demo(conn)


def _seed_demo(conn: sqlite3.Connection):
    row = conn.execute("SELECT COUNT(*) AS c FROM clients").fetchone()
    if row["c"] > 0:
        return

    now = datetime.utcnow().isoformat()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO clients (
            display_name, is_married, monthly_inflow, monthly_outflow,
            insurance_deductibles, schwab_label, created_at, updated_at
        ) VALUES (?, 1, 15000, 11000, 2500, 'Schwab Brokerage', ?, ?)
        """,
        ("Smith Family", now, now),
    )
    client_id = cur.lastrowid
    cur.execute(
        """
        INSERT INTO persons (client_id, role, full_name, date_of_birth, ssn_last_four)
        VALUES
            (?, 'client1', 'John Smith', '1965-03-15', '1234'),
            (?, 'client2', 'Jane Smith', '1967-08-22', '5678')
        """,
        (client_id, client_id),
    )
    accounts = [
        ("retirement_c1", "IRA", "Traditional IRA", "4521", None, None, 0),
        ("retirement_c1", "Roth IRA", "Roth IRA", "8832", None, None, 1),
        ("retirement_c2", "IRA", "Traditional IRA", "1190", None, None, 0),
        ("retirement_c2", "Roth IRA", "Roth IRA", "7743", None, None, 1),
        ("non_retirement", "Brokerage", "Joint Brokerage", "3301", None, None, 0),
        ("non_retirement", "Joint", "Pinnacle Joint Checking", "8820", None, None, 1),
        ("trust", "Residence", "Primary Residence Trust", "", None, "123 Peachtree St, Atlanta, GA", 0),
        ("liability", "Mortgage", "Home Mortgage", "", 3.25, None, 0),
    ]
    for cat, atype, label, last4, rate, addr, order in accounts:
        cur.execute(
            """
            INSERT INTO accounts (
                client_id, category, account_type, label, account_last_four,
                interest_rate, property_address, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (client_id, cat, atype, label, last4, rate, addr, order),
        )
    conn.commit()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def parse_json_field(value: str | None, default=None):
    if default is None:
        default = {}
    if not value:
        return default
    return json.loads(value)


def age_from_dob(dob_str: str) -> int:
    dob = date.fromisoformat(dob_str)
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
