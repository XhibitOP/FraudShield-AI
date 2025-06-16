import json
from fraud_ai_system.backend.src.db import get_db
import os

# Load your transaction JSON file
DATA_FILE_PATH = os.path.join("fraud_ai_system", "data", "transactions.json")  # adjust path if needed

def load_transactions():
    try:
        with open(DATA_FILE_PATH, "r") as f:
            data = json.load(f)
            print(f"📦 Loaded {len(data)} transactions from file.")
            return data
    except Exception as e:
        print(f"❌ Error reading data file: {e}")
        return []

def insert_transactions(transactions):
    db = get_db()
    transactions_col = db["transactions"]

    inserted_count = 0
    for txn in transactions:
        try:
            if not txn.get("transaction_id"):
                print("⚠️ Skipping transaction with no transaction_id.")
                continue
            existing = transactions_col.find_one({"transaction_id": txn["transaction_id"]})
            if not existing:
                transactions_col.insert_one(txn)
                inserted_count += 1
        except Exception as e:
            print(f"❌ Error inserting transaction: {e}")

    print(f"✅ Inserted {inserted_count} new transactions into MongoDB.")

if __name__ == "__main__":
    transactions = load_transactions()
    insert_transactions(transactions)
