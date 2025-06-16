import pandas as pd
from datetime import datetime
import numpy as np
import joblib
import os

MODEL_PATH = os.getenv("MODEL_PATH")  # get from environment variable
if not MODEL_PATH:
    MODEL_PATH = os.path.join("models", "risk_model.pkl")

def load_model():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = os.path.join(base_dir, "models", "risk_model.pkl")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found at {model_path}")

    model = joblib.load(model_path)
    # model is just the classifier, not a tuple
    return model

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    a = np.sin(delta_phi/2.0)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(delta_lambda/2.0)**2
    return R * 2 * np.arcsin(np.sqrt(a))

def extract_features(txn):
    features = {}

    # Amount
    features['amount'] = float(txn.get('amount'))
    if isinstance(features['amount'], dict):
        features['amount'] = float(features['amount'].get('$numberDecimal', 0))
    # Transaction Type (label encode later)
    features['transactionType'] = txn.get('transactionType', 'unknown')

    # Status (label encode later)
    features['status'] = txn.get('status', 'unknown')

    # Date-time features
    created_at = txn.get('createdAt', {}).get('$date', None)
    if created_at:
        dt = pd.to_datetime(created_at)
        features['createdAt_unix'] = int(dt.timestamp())
        features['createdAt_hour'] = dt.hour
        features['createdAt_weekday'] = dt.weekday()
    else:
        features['createdAt_unix'] = 0
        features['createdAt_hour'] = 0
        features['createdAt_weekday'] = 0

    # metaData latitude & longitude
    meta = txn.get('metaData', {})
    features['meta_lat'] = float(meta.get('lat') or 0)
    features['meta_long'] = float(meta.get('long') or 0)

    # Vendor info
    features['vendorId'] = txn.get('vendorId', 'unknown')
    features['vendorServiceType'] = txn.get('vendorServiceType', 'unknown')

    # Partner commission amount
    partner = txn.get('partnerDetails', {})
    features['partner_commissionAmount'] = float(partner.get('commissionAmount', 0))

    # Admin wallet balances
    admin = txn.get('adminDetails', {})
    features['admin_oldMainWalletBalance'] = float(admin.get('oldMainWalletBalance', 0))
    features['admin_newMainWalletBalance'] = float(admin.get('newMainWalletBalance', 0))

    # Operator keys
    operator = txn.get('operator', {})
    features['operator_key1'] = operator.get('key1', 'unknown')
    features['operator_key2'] = operator.get('key2', 'unknown')

    # Mobile number (can encode or use as is)
    features['mobileNumber'] = txn.get('mobileNumber', 'unknown')

    # checkStatus length
    check_status = txn.get('checkStatus', [])
    features['checkStatus_count'] = len(check_status)

    # Geo distance can be computed if you have lat/lon of vendor or admin etc.
    # Assuming vendor lat/long not available, skip or add if you have it

    return features

def predict(model, txn):
    # Extract amount safely
    amount_value = txn.get('amount')
    if isinstance(amount_value, dict):
        amount_value = amount_value.get('value') or amount_value.get('amount')
    try:
        amount = float(amount_value)
    except (TypeError, ValueError):
        amount = 0.0  # fallback if conversion fails

    # Extract hour from 'CreatedAT' field
    hour = 0
    created_at_str = txn.get('CreatedAT')
    if created_at_str:
        try:
            dt = datetime.fromisoformat(created_at_str)
            hour = dt.hour
        except Exception:
            hour = 0  # fallback if parsing fails

    features = {
        'amount': amount,
        'hour': hour,
        # Add other features here as needed
    }

    X = pd.DataFrame([features])

    prediction = model.predict(X)
    risk_score = model.predict_proba(X)[:, 1]  # assuming binary classifier

    return {
        "prediction": int(prediction[0]),
        "risk_score": float(risk_score[0])
    }
