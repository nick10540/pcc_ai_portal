"""PCC AI Portal — Custom Backend
FastAPI app: auth middleware + PII detector + billing service
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth.router import router as auth_router
from src.pdpa.router import router as pdpa_router
from src.billing.router import router as billing_router

app = FastAPI(title="PCC AI Portal Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # open-webui
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(pdpa_router, prefix="/guardrails", tags=["pdpa"])
app.include_router(billing_router, prefix="/billing", tags=["billing"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhooks/budget-alert")
async def budget_alert(payload: dict):
    """รับ webhook จาก LiteLLM เมื่อ budget ถึง threshold"""
    # TODO: ส่ง LINE Notify / email
    return {"received": True, "payload": payload}
