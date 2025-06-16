import json
import os
from datetime import datetime
from pymongo.errors import PyMongoError
from fraud_ai_system.backend.src.db import get_db


def fetch_transactions(limit: int = 100, name: str = None, is_fraud: bool = None, risk_level: str = None) -> list:
    try:
        db = get_db()
        predict_col = db["predict"]
        print("logging predict col", predict_col)
        print("Connected DB:", db.name)  # should be 'Xhibit'
        print("Collection name:", predict_col.name)  # should be 'predict'

        query = {}

        if name:
            query["name"] = {"$regex": name, "$options": "i"}

        if is_fraud is not None:
            query["is_fraud"] = is_fraud

        if risk_level:
            if risk_level == "low":
                query["risk_score"] = {"$lte": 0.3}
            elif risk_level == "medium":
                query["risk_score"] = {"$gt": 0.3, "$lte": 0.7}
            elif risk_level == "high":
                query["risk_score"] = {"$gt": 0.7}

        transactions = list(predict_col.find(query).sort("timestamp", -1).limit(limit))
        print(f"✅ Fetched {len(transactions)} filtered transactions from DB.")
        return transactions
    except PyMongoError as e:
        print(f"❌ Error fetching filtered transactions: {e}")
        return []


def save_suspicious_transaction(txn):
    try:
        db = get_db()
        fraud_data_col = db["fraud_data"]
        txn_id = txn.get("transaction_id") or txn.get("transactionId")
        if not txn_id:
            print("⚠️ Transaction missing 'transaction_id'. Skipping.")
            return

        existing = fraud_data_col.find_one({"transaction_id": txn_id})
        if existing:
            print(f"ℹ️ Transaction {txn_id} already exists. Skipping.")
            return

        # 🔍 Run fraud analysis using your updated engine
        from fraud_ai_system.backend.src.apply_rules import process_transaction
        from fraud_ai_system.backend.src.ml_model import predict
        fraud_result = process_transaction(txn, model=None)  # Load actual model if needed

        txn["is_fraud"]     = fraud_result.get("rules_flagged", False) or fraud_result.get("ml_prediction", 0)
        txn["risk_score"]   = fraud_result.get("risk_score", 0.0)
        txn["reasons"]      = fraud_result.get("reasons", [])
        txn["triggers"]     = fraud_result.get("triggers", [])  # ✅ Main Update
        txn["inserted_at"]  = datetime.utcnow()

        fraud_data_col.insert_one(txn)
        print(f"✅ Suspicious transaction saved: {txn_id}")

    except PyMongoError as e:
        print(f"❌ Failed to insert suspicious transaction: {e}")

        print(f"❌ Failed to insert suspicious transaction: {e}")


def load_data_from_file(file_path="fraud_ai_system/data/transactions.json"):
    try:
        db = get_db()
        predict_col = db["predict"]

        # Fetch and log some documents
        print("🔄 Scanning for new transactions...")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"📁 File not found: {file_path}")

        with open(file_path, "r") as f:
            transactions = json.load(f)

        if not isinstance(transactions, list):
            raise ValueError("❌ JSON must contain a list of transactions.")

        inserted = 0
        for txn in transactions:
            txn_id = txn.get("transaction_id") or txn.get("transactionId")
            if not txn_id or predict_col.find_one({"transaction_id": txn_id}):
                continue
            predict_col.insert_one(txn)
            inserted += 1

        print(f"✅ Inserted {inserted} new transactions from file.")
        return inserted

    except (json.JSONDecodeError, FileNotFoundError, ValueError, PyMongoError) as e:
        print(f"❌ Error loading data from file: {e}")
        return 0


def insert_transactions(txns):
    try:
        db = get_db()
        predict_col = db["predict"]
        print("logging predict col",predict_col)
        inserted = 0

        for txn in txns:
            txn_id = txn.get("transaction_id") or txn.get("transactionId")
            if not txn_id:
                print("⚠️ Skipping transaction with missing transactionId")
                continue

            existing = predict_col.find_one({"transactionId": txn_id})
            if existing:
                print(f"ℹ️ Transaction {txn_id} already exists in DB. Skipping.")
                continue

            try:
                result = predict_col.insert_one(txn)
                if result.inserted_id:
                    inserted += 1
                    print(f"✅ Inserted transaction {txn_id} with id {result.inserted_id}")
                else:
                    print(f"❌ Failed to insert transaction {txn_id} (no inserted_id returned)")
            except Exception as e:
                print(f"❌ Exception inserting transaction {txn_id}: {e}")

        print(f"Total inserted: {inserted}")
        return inserted

    except Exception as e:
        print(f"❌ insert_transactions encountered an error: {e}")
        return 0
