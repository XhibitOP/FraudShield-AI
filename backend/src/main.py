import sys
import os
import threading
import time
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fraud_ai_system.backend.src.apply_rules import apply_rules
from fraud_ai_system.backend.src.ml_model import predict,load_model
from fraud_ai_system.backend.src.api import router
from fraud_ai_system.backend.src.db_handler import fetch_transactions, save_suspicious_transaction

model = load_model()
# Add project path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize FastAPI
app = FastAPI()
app.include_router(router)

# Apply CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fraud-detection-fe.vercel.app/"],  # Change to your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def process_transaction(transaction: dict) -> dict:
    try:
        rule_results = apply_rules(transaction)
        ml_results = predict(model,transaction)
    except Exception as e:
        print(f"❌ Error processing transaction {transaction.get('transaction_id', 'unknown')}: {e}")
        return {
            "rules_flagged": False,
            "ml_prediction": 0,
            "risk_score": 0.0
        }

    return {
        "rules_flagged": rule_results,
        "ml_prediction": ml_results.get("prediction", 0),
        "risk_score": ml_results.get("risk_score", 0.0)
    }

def auto_scan_loop():
    """Continuously scan transactions every 60 seconds."""
    while True:
        print("🔄 Scanning for new transactions...")
        try:
            transactions = fetch_transactions()
            print(f"✅ Fetched {len(transactions)} transactions from MongoDB.")
        except Exception as e:
            print(f"❌ Failed to fetch transactions: {e}")
            transactions = []

        for txn in transactions:
            result = process_transaction(txn)
            if result["rules_flagged"] or result["ml_prediction"] == 1:
                try:
                    save_suspicious_transaction({**txn, **result})
                    print(f"🚨 Suspicious transaction saved: {txn.get('transaction_id')}")
                except Exception as e:
                    print(f"❌ Failed to save suspicious transaction {txn.get('transaction_id')}: {e}")

        print("✅ Scan complete. Waiting for next scan...")
        time.sleep(60)  # wait 60 seconds

@app.on_event("startup")
def start_background_tasks():
    """Start background scanning thread on FastAPI startup."""
    scan_thread = threading.Thread(target=auto_scan_loop)
    scan_thread.daemon = True
    scan_thread.start()
