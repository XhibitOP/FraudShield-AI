from datetime import datetime
import re
from fraud_ai_system.backend.src.ml_model import predict
from typing import Any, Dict, List, Tuple

# ---------- constants -------------------------------------------------------
HIGH_AMOUNT_WT          = 0.20
ODD_HOUR_WT             = 0.20
NIGHT_BIG_TXN_WT        = 0.20
WALLET_MISMATCH_WT      = 0.10
BAD_UTR_WT              = 0.20
PRIVATE_IP_WT           = 0.10
DEVICE_CHANGE_WT        = 0.20
ZERO_GEO_WT             = 0.20
FLAGGED_BENEF_WT        = 0.30

RISK_THRESHOLD = 0.70      # ≥ this → fraud

# ---------- helpers ---------------------------------------------------------
def g(doc: Dict[str, Any], *path, default=None):
    """Get nested value like g(txn,'partnerDetails','amount')."""
    cur = doc
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur

def parse_timestamp(txn: Dict[str, Any]) -> datetime | None:
    # 1️⃣ explicit field
    ts_raw = txn.get("timestamp")
    # 2️⃣ first checkStatus.date
    if not ts_raw:
        ts_raw = g(txn, "checkStatus", 0, "date")
    if not ts_raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(ts_raw, fmt)
        except ValueError:
            continue
    return None

def extract_lat_long(txn: Dict[str, Any]) -> Tuple[float, float]:
    lat = txn.get("lat")
    lon = txn.get("long")
    if lat is None or lon is None:
        lat = g(txn, "location", "latitude", default=0.0)
        lon = g(txn, "location", "longitude", default=0.0)
    return float(lat), float(lon)

# ---------- core rules ------------------------------------------------------
def apply_rules(txn: Dict[str, Any], history: Dict[str, Any] | None = None
                ) -> Tuple[bool, float, List[str], List[Dict[str, str]]]:
    reasons: List[str] = []
    fraud_triggers: List[Dict[str, str]] = []
    risk = 0.0

    amount = float(g(txn, "partnerDetails", "amount", default=0))
    debit  = float(g(txn, "partnerDetails", "debit", default=0))
    credit = float(g(txn, "partnerDetails", "credit", default=0))
    tds    = float(g(txn, "partnerDetails", "TDS",   default=0))

    oldMainWalletBalance = float(g(txn, "adminDetails", "oldMainWalletBalance", default=0))
    newMainWalletBalance = float(g(txn, "adminDetails", "newMainWalletBalance", default=0))

    ip_addr = txn.get("ipAddress", g(txn, "metaData", "ipAddress", default=""))
    imei    = txn.get("imeiNumber", "")
    utr     = txn.get("vendorUtrNumber", "")

    lat, lon = extract_lat_long(txn)
    txn_dt   = parse_timestamp(txn)

    # Rule 1: high amount
    if amount > 1e5:
        risk += HIGH_AMOUNT_WT
        reasons.append(f"High amount ₹{amount:,.0f}")
        fraud_triggers.append({
            "type": "Amount",
            "blocked": f"₹{amount:,.0f}"
        })

    # Rule 2: odd hours
    if txn_dt and 1 <= txn_dt.hour <= 5:
        risk += ODD_HOUR_WT
        reasons.append(f"Transaction at odd hour ({txn_dt.hour} h)")
        fraud_triggers.append({
            "type": "Transaction Time",
            "blocked": txn_dt.strftime("%H:%M:%S")
        })

    # Rule 3: huge night txn
    if txn_dt and txn_dt.hour in (1, 2, 3) and amount > 2e5:
        risk += NIGHT_BIG_TXN_WT
        reasons.append("Very high amount during 1–3 AM window")
        fraud_triggers.append({
            "type": "Night High Amount",
            "blocked": f"₹{amount:,.0f} at {txn_dt.strftime('%H:%M')}"
        })

    # Rule 4: wallet mismatch
    if abs((oldMainWalletBalance - debit + credit - tds) - newMainWalletBalance) > 1:
        risk += WALLET_MISMATCH_WT
        reasons.append("Admin wallet balance mismatch")
        fraud_triggers.append({
            "type": "Wallet Mismatch",
            "blocked": f"{oldMainWalletBalance=} → {newMainWalletBalance=}"
        })

    # Rule 5: UTR malformed / missing
    if not utr or not re.fullmatch(r"[A-Za-z0-9]{10,}", utr):
        risk += BAD_UTR_WT
        reasons.append("Malformed or missing UTR number")
        fraud_triggers.append({
            "type": "UTR Number",
            "blocked": utr or "MISSING"
        })

    # Rule 6: private / reserved IP
    if ip_addr.startswith(("192.168.", "10.", "172.16.")):
        risk += PRIVATE_IP_WT
        reasons.append("Private / reserved IP")
        fraud_triggers.append({
            "type": "IP Address",
            "blocked": ip_addr
        })

    # Rule 7: device change
    if history and history.get("last_imei") and imei != history["last_imei"]:
        risk += DEVICE_CHANGE_WT
        reasons.append("IMEI changed vs. previous device")
        fraud_triggers.append({
            "type": "IMEI",
            "blocked": f"{imei} (previous: {history['last_imei']})"
        })

    # Rule 8: zero / invalid geo
    if lat == 0.0 and lon == 0.0:
        risk += ZERO_GEO_WT
        reasons.append("Invalid geo-coordinates (0,0)")
        fraud_triggers.append({
            "type": "GeoCoordinates",
            "blocked": f"{lat}, {lon}"
        })

    # Rule 9: flagged beneficiary
    if history:
        acct = g(txn, "moneyTransferBeneficiaryDetails", "accountNumber", default="") + \
               g(txn, "moneyTransferBeneficiaryDetails", "ifsc", default="")
        if acct and acct in history.get("flagged_accounts", set()):
            risk += FLAGGED_BENEF_WT
            reasons.append("Previously flagged beneficiary reused")
            fraud_triggers.append({
                "type": "Beneficiary",
                "blocked": acct
            })

    is_fraud = risk >= RISK_THRESHOLD
    return is_fraud, round(risk, 3), reasons, fraud_triggers


# ---------- wrapper ---------------------------------------------------------
def check_transaction(txn: Dict[str, Any], history: Dict[str, Any] | None = None) -> Dict[str, Any]:
    fraud, score, reasons, triggers = apply_rules(txn, history)


    if score >= 0.8:
        level, action = "High",   "Cancel"
    elif score >= 0.5:
        level, action = "Medium", "Pending"
    else:
        level, action = "Low",    "Approve"

    return {
        "status":      "fraudulent" if fraud else "genuine",
        "risk_score":  score,
        "risk_level":  level,
        "action":      action,
        "reasons":     reasons,
        "triggers":    triggers
    }
# ---------- unified processor ----------------------------------------------
def process_transaction(transaction: dict, model=None, history: dict = None) -> dict:
    try:
        # Run rule-based check
        is_fraud, risk_score_rules, reasons, triggers = apply_rules(transaction, history)

        
        # Run ML model prediction
        ml_results = predict(model, transaction) if model else {"prediction": 0, "risk_score": 0.0}
    
        return {
            "rules_flagged": is_fraud,
            "ml_prediction": ml_results.get("prediction", 0),
            "risk_score": max(risk_score_rules, ml_results.get("risk_score", 0.0)),  # max or avg
            "reasons": reasons,
            "triggers": triggers,
        }

    except Exception as e:
        print(f"❌ Error processing transaction {transaction.get('transactionId', 'unknown')}: {e}")
        return {
            "rules_flagged": False,
            "ml_prediction": 0,
            "risk_score": 0.0,
            "reasons": ["Error processing transaction"]
        }
