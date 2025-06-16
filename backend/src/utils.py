from datetime import datetime

def parse_date(date_str, fmt='%Y-%m-%d %H:%M:%S'):
    try:
        return datetime.strptime(date_str, fmt)
    except (ValueError, TypeError) as e:
        print(f"Date parse error for '{date_str}': {e}")
        return None

def extract_features(transaction):
    parsed_time = parse_date(transaction.get('timestamp'))
    features = {
        'amount': transaction.get('amount', 0),
        'hour': parsed_time.hour if parsed_time else 0,
        # Future: add weekday, location anomalies, device ID flags, etc.
    }
    return features

def extract_features(transaction: dict) -> dict:
    partner = transaction.get("partnerDetails", {}) or {}
    admin = transaction.get("adminDetails", {}) or {}
    agent = transaction.get("agentDetails", {}) or {}
    meta = transaction.get("metaData", {}) or {}
    operator = transaction.get("operator", {}) or {}

    features = {
        "partner_amount": partner.get("amount", 0),
        "partner_credit": partner.get("credit", 0),
        "partner_debit": partner.get("debit", 0),
        "partner_TDS": partner.get("TDS", 0),
        "partner_GST": partner.get("GST", 0),
        "admin_commission": admin.get("commissionAmount", 0),
        "admin_credited": admin.get("creditedAmount", 0),
        "admin_TDS": admin.get("TDSAmount", 0),
        "agent_commission": agent.get("commissionAmount", 0),
        "agent_credited": agent.get("creditedAmount", 0),
        "agent_TDS": agent.get("TDSAmount", 0),
        "ip_address": transaction.get("ipAddress", meta.get("ipAddress", "")),
        "device_type": meta.get("deviceType", ""),
        "latitude": meta.get("lat", ""),
        "longitude": meta.get("long", ""),
        "operator_ifsc": operator.get("key2", ""),
        "mobile_number": operator.get("mobileNumber", "")
    }

    return features
