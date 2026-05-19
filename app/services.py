import json
from datetime import datetime

from app.calculations import compute_report, validate_balances_complete
from app.database import age_from_dob, db_cursor, parse_json_field, row_to_dict


def list_clients(db):
    rows = db.execute(
        """
        SELECT c.*,
               (
                   SELECT MAX(r.created_at)
                   FROM reports r
                   WHERE r.client_id = c.id
               ) AS last_report_at
        FROM clients c
        ORDER BY c.display_name
        """
    ).fetchall()
    return [row_to_dict(r) for r in rows]


def get_client_bundle(db, client_id: int):
    client = row_to_dict(
        db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    )
    if not client:
        return None

    persons = [
        row_to_dict(r)
        for r in db.execute(
            "SELECT * FROM persons WHERE client_id = ? ORDER BY role",
            (client_id,),
        ).fetchall()
    ]
    for person in persons:
        person["age"] = age_from_dob(person["date_of_birth"])

    accounts = [
        row_to_dict(r)
        for r in db.execute(
            "SELECT * FROM accounts WHERE client_id = ? ORDER BY category, sort_order, id",
            (client_id,),
        ).fetchall()
    ]

    return {"client": client, "persons": persons, "accounts": accounts}


def save_client(db, payload: dict) -> int:
    now = datetime.utcnow().isoformat()
    client_id = payload.get("id")

    with db_cursor(db) as cur:
        if client_id:
            cur.execute(
                """
                UPDATE clients SET
                    display_name = ?, is_married = ?, monthly_inflow = ?,
                    monthly_outflow = ?, insurance_deductibles = ?,
                    schwab_label = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["display_name"],
                    1 if payload.get("is_married") else 0,
                    payload["monthly_inflow"],
                    payload["monthly_outflow"],
                    payload.get("insurance_deductibles", 0),
                    payload.get("schwab_label", "Schwab Investment Account"),
                    now,
                    client_id,
                ),
            )
            cur.execute("DELETE FROM persons WHERE client_id = ?", (client_id,))
            cur.execute("DELETE FROM accounts WHERE client_id = ?", (client_id,))
        else:
            cur.execute(
                """
                INSERT INTO clients (
                    display_name, is_married, monthly_inflow, monthly_outflow,
                    insurance_deductibles, schwab_label, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["display_name"],
                    1 if payload.get("is_married") else 0,
                    payload["monthly_inflow"],
                    payload["monthly_outflow"],
                    payload.get("insurance_deductibles", 0),
                    payload.get("schwab_label", "Schwab Investment Account"),
                    now,
                    now,
                ),
            )
            client_id = cur.lastrowid

        for person in payload.get("persons", []):
            if not person.get("full_name"):
                continue
            cur.execute(
                """
                INSERT INTO persons (client_id, role, full_name, date_of_birth, ssn_last_four)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    client_id,
                    person["role"],
                    person["full_name"],
                    person["date_of_birth"],
                    person.get("ssn_last_four", ""),
                ),
            )

        for idx, account in enumerate(payload.get("accounts", [])):
            if not account.get("label"):
                continue
            cur.execute(
                """
                INSERT INTO accounts (
                    client_id, category, account_type, label, account_last_four,
                    interest_rate, property_address, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_id,
                    account["category"],
                    account["account_type"],
                    account["label"],
                    account.get("account_last_four", ""),
                    account.get("interest_rate"),
                    account.get("property_address"),
                    idx,
                ),
            )

    return client_id


def delete_client(db, client_id: int):
    with db_cursor(db) as cur:
        cur.execute("DELETE FROM clients WHERE id = ?", (client_id,))


def latest_report_balances(db, client_id: int) -> dict:
    row = db.execute(
        """
        SELECT balances_json FROM reports
        WHERE client_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (client_id,),
    ).fetchone()
    if not row:
        return {}
    return parse_json_field(row["balances_json"])


def list_reports(db, client_id: int):
    rows = db.execute(
        """
        SELECT id, quarter_label, report_date, created_at
        FROM reports
        WHERE client_id = ?
        ORDER BY created_at DESC
        """,
        (client_id,),
    ).fetchall()
    return [row_to_dict(r) for r in rows]


def get_report(db, report_id: int):
    row = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        return None
    report = row_to_dict(row)
    report["balances"] = parse_json_field(report.pop("balances_json"))
    report["calculations"] = parse_json_field(report.pop("calculations_json"))
    bundle = get_client_bundle(db, report["client_id"])
    return {"report": report, **bundle}


def save_report(db, client_id: int, payload: dict) -> tuple[int, dict]:
    bundle = get_client_bundle(db, client_id)
    if not bundle:
        raise ValueError("Client not found")

    balances = payload.get("balances", {})
    missing = validate_balances_complete(bundle["client"], bundle["accounts"], balances)
    if missing:
        raise ValueError(f"Missing required balances: {', '.join(missing)}")

    calculations = compute_report(bundle["client"], bundle["accounts"], balances)
    now = datetime.utcnow().isoformat()

    with db_cursor(db) as cur:
        cur.execute(
            """
            INSERT INTO reports (
                client_id, quarter_label, report_date, balances_json,
                calculations_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                payload["quarter_label"],
                payload.get("report_date", now[:10]),
                json.dumps(balances),
                json.dumps(calculations),
                now,
            ),
        )
        report_id = cur.lastrowid

    return report_id, calculations
