from __future__ import annotations

from typing import Any


def compute_report(client: dict, accounts: list[dict], balances: dict[str, Any]) -> dict:
    """Compute SACS and TCC totals per PRD rules."""
    inflow = float(client["monthly_inflow"])
    outflow = float(client["monthly_outflow"])
    insurance = float(client["insurance_deductibles"])

    excess = inflow - outflow
    private_reserve_target = (6 * outflow) + insurance

    private_reserve_balance = _balance(balances, "private_reserve")
    schwab_balance = _balance(balances, "schwab_investment")

    c1_retirement = 0.0
    c2_retirement = 0.0
    non_retirement = 0.0
    trust_value = 0.0
    liabilities_total = 0.0

    account_details: list[dict] = []

    for account in accounts:
        key = str(account["id"])
        bal = _balance(balances, key)
        cash = _balance(balances, f"{key}_cash")
        cat = account["category"]
        detail = {
            **account,
            "balance": bal,
            "cash_balance": cash,
        }
        account_details.append(detail)

        if cat == "retirement_c1":
            c1_retirement += bal
        elif cat == "retirement_c2":
            c2_retirement += bal
        elif cat == "non_retirement":
            non_retirement += bal
        elif cat == "trust":
            trust_value += bal
        elif cat == "liability":
            liabilities_total += bal

    grand_total = c1_retirement + c2_retirement + non_retirement + trust_value

    return {
        "sacs": {
            "inflow": inflow,
            "outflow": outflow,
            "excess": excess,
            "private_reserve_target": private_reserve_target,
            "private_reserve_balance": private_reserve_balance,
            "schwab_balance": schwab_balance,
        },
        "tcc": {
            "client1_retirement_total": c1_retirement,
            "client2_retirement_total": c2_retirement,
            "non_retirement_total": non_retirement,
            "trust_value": trust_value,
            "grand_total": grand_total,
            "liabilities_total": liabilities_total,
        },
        "accounts": account_details,
    }


def _balance(balances: dict, key: str) -> float:
    raw = balances.get(key)
    if raw is None or raw == "":
        return 0.0
    return float(raw)


def validate_balances_complete(client: dict, accounts: list[dict], balances: dict) -> list[str]:
    missing: list[str] = []
    for account in accounts:
        key = str(account["id"])
        if key not in balances or balances[key] in (None, ""):
            missing.append(account["label"])
    for sacs_key, label in [
        ("private_reserve", "Private Reserve Balance"),
        ("schwab_investment", "Schwab Investment Balance"),
    ]:
        if sacs_key not in balances or balances[sacs_key] in (None, ""):
            missing.append(label)
    return missing
