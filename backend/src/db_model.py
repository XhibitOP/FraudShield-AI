from pydantic import BaseModel, Field
from typing import List, Optional

class PartnerDetails(BaseModel):
    oldMainWalletBalance: float
    newMainWalletBalance: float
    amount: float
    credit: float
    debit: float
    TDS: float

class AdminDetails(BaseModel):
    oldMainWalletBalance: float
    newMainWalletBalance: float

class CheckStatusItem(BaseModel):
    vendorApiResponse: str
    date: str
    ipAddress: Optional[str] = ""
    deviceType: Optional[str] = ""
    imeiNumber: Optional[str] = ""

class MetaData(BaseModel):
    ipAddress: Optional[str] = ""
    deviceType: Optional[str] = ""
    imeiNumber: Optional[str] = ""

class MoneyTransferBeneficiaryDetails(BaseModel):
    accountNumber: Optional[str] = ""
    ifsc: Optional[str] = ""

class Operator(BaseModel):
    key1: Optional[str] = ""
    key2: Optional[str] = ""
    key3: Optional[str] = ""

class Transaction(BaseModel):
    transaction_id: str = Field(..., alias="transactionId")
    client_ref_id: str = Field(..., alias="clientRefId")
    transaction_type: str = Field(..., alias="transactionType")
    status: str
    vendor_utr_number: str = Field(..., alias="vendorUtrNumber")
    partner_details: PartnerDetails = Field(..., alias="partnerDetails")
    admin_details: AdminDetails = Field(..., alias="adminDetails")
    check_status: List[CheckStatusItem] = Field(..., alias="checkStatus")
    meta_data: MetaData = Field(..., alias="metaData")
    money_transfer_beneficiary_details: MoneyTransferBeneficiaryDetails = Field(..., alias="moneyTransferBeneficiaryDetails")
    operator: Operator
    amount: float
    credit: float
    debit: float
    TDS: float
    GST: float
    createdAt: Optional[str] = None
    mobileNumber: Optional[str] = ""

    class Config:
        validate_by_name = True
