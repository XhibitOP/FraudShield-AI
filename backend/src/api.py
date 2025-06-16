from fastapi import APIRouter, Form, UploadFile, File, HTTPException,Query
from typing import List, Optional
from fraud_ai_system.backend.src.db_model import Transaction  # Your Pydantic model
from fraud_ai_system.backend.src.ml_model import load_model, predict
from fraud_ai_system.backend.src.apply_rules import check_transaction
from fraud_ai_system.backend.src.utils import extract_features
from fraud_ai_system.backend.src.db_handler import insert_transactions,fetch_transactions
from fraud_ai_system.backend.src.db import get_db
from bson.json_util import dumps,loads
from datetime import datetime
from bson import Binary
from fastapi.responses import JSONResponse
import json
import logging
import traceback

logger = logging.getLogger("fraud_ai_system")
router = APIRouter()
model = load_model()

@router.get("/")
async def root():
    return {"message": "API is running"}

@router.get("/predict")
async def predict_from_db(
    limit: int = 100,
    name: Optional[str] = Query(None, description="Filter by name"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level (low, medium, high)")
):
    try:
        db = get_db()
        raw_collection = db["transaction.predict"]
        fraud_collection = db["transaction.fraud_data"]

        # Fetch raw transactions
        query = {}
        if name:
            query["name"] = {"$regex": name, "$options": "i"}

        transactions = list(raw_collection.find(query).limit(limit))

        results = []
        for txn in transactions:
            try:
                result = check_transaction(txn)

                # Optional frontend filter (e.g., only save if High risk)
                if risk_level and result["risk_level"].lower() != risk_level.lower():
                    continue

                # Save only if fraudulent
                if result["status"] == "fraudulent":
                    fraud_doc = {
                        "transactionId": txn.get("transactionId") or txn.get("transaction_id"),
                        **txn,
                        **result
                    }
                    results.append(fraud_doc)

            except Exception as err:
                logger.warning(f"Skipping bad transaction: {err}")

        # Save frauds only
        if results:
            fraud_collection.delete_many({})  # optional clear
            fraud_collection.insert_many(results)

        return {
            "stored_fraud_count": len(results),
            "fraud_results_preview": results[:10]  # preview first few
        }
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed")


    
@router.post("/fraud")
async def insert_transactions_api(txns: List[Transaction]):
    try:
        print(f"Received {len(txns)} transactions")
        txns_dicts = [txn.dict() for txn in txns]
        inserted_count = insert_transactions(txns_dicts)
        return {"inserted_transactions": inserted_count}
    except Exception as e:
        # You can log the error here if needed
        raise HTTPException(status_code=500, detail=f"Error inserting transactions: {e}")


@router.get("/suspicious")
async def get_suspicious_transactions(limit: int = 100):
    """
    Fetch suspicious/fraudulent transactions from the 'fraud_data' collection in the 'transaction' database.
    """
    try:
        db = get_db()
        fraud_collection = db["fraud_data"]

        suspicious = list(fraud_collection.find())
        json_str = dumps(suspicious)       # Safely serialize ObjectId, datetime, etc.
        json_obj = json.loads(json_str)    # Convert back to Python dict/list

        return JSONResponse(content={
            "count": len(json_obj),
            "data": json_obj
        })


    except Exception as e:
        print("Error fetching suspicious transactions:", e)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": str(e)})
    

@router.post("/suspicious")
async def add_to_blocklist(
    type: str = Form(...),
    value: str = Form(...),
    remarks: str = Form(...),
    attachment: UploadFile = File(None)
):
    try:
        db = get_db()
        block_col = db["blocked_entities"]

        existing = block_col.find_one({"type": type, "value": value})
        if existing:
            return {"message": "Already blocked", "status": "exists"}

        doc = {
            "type": type,
            "value": value,
            "remarks": remarks,
            "created_at": datetime.utcnow()
        }

        if attachment:
            file_data = await attachment.read()  # read file bytes
            doc["attachment"] = Binary(file_data)
            doc["attachment_name"] = attachment.filename
            doc["attachment_mime"] = attachment.content_type

        result = block_col.insert_one(doc)
        return {"message": "✅ Blocked entry saved", "id": str(result.inserted_id)}

    except Exception as e:
        return {"message": f"❌ Error: {e}", "status": "error"}
