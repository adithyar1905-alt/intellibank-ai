from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.v1.accounts import router as accounts_router
from app.api.v1.aml import router as aml_router
from app.api.v1.auth import router as auth_router
from app.api.v1.banking_assistant import router as banking_assistant_router
from app.api.v1.customers import router as customers_router
from app.api.v1.credit_scoring import router as credit_scoring_router
from app.api.v1.fraud import router as fraud_router
from app.api.v1.loans import router as loans_router
from app.api.v1.transactions import router as transactions_router

app = FastAPI(title="IntelliBank API")
allowed_origins = [
    origin.strip()
    for origin in get_settings().cors_allowed_origins.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(customers_router, prefix="/api/v1")
app.include_router(accounts_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(loans_router, prefix="/api/v1")
app.include_router(fraud_router, prefix="/api/v1")
app.include_router(credit_scoring_router, prefix="/api/v1")
app.include_router(aml_router, prefix="/api/v1")
app.include_router(banking_assistant_router, prefix="/api/v1")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
