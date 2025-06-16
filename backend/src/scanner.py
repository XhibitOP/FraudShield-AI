# fraud_ai_system/backend/src/scanner.py

from fraud_ai_system.backend.src.db_handler import fetch_transactions, save_suspicious_transaction
from fraud_ai_system.backend.src.apply_rules import apply_rules
from fraud_ai_system.backend.src.ml_model import predict,load_model

model = load_model()

def scan_and_save_new_fraud():
    try:
        transactions = fetch_transactions(limit=200)  # Fetch latest 200
        for txn in transactions:
            try:
                txn_id = txn.get("transaction_id") or txn.get("transactionId")
                if not txn_id:
                    continue

                rules_flagged = apply_rules(txn)
                ml_result = predict(model,txn)
                risk_score = ml_result.get("risk_score", 0.0)
                ml_prediction = ml_result.get("prediction", 0)

                if rules_flagged or ml_prediction == 1:
                    txn.update({
                        "rules_flagged": rules_flagged,
                        "ml_prediction": ml_prediction,
                        "risk_score": risk_score
                    })
                    save_suspicious_transaction(txn)

            except Exception as err:
                print(f"❌ Error processing transaction: {err}")

        print("✅ Auto-scan complete. Suspicious data updated.")
    except Exception as e:
        print(f"❌ Error in auto-scanner: {e}")
