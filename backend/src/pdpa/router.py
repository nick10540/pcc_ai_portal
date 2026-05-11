"""PDPA PII Detector — ภาษาไทย + English
LiteLLM เรียก endpoint นี้ก่อนส่ง request ไป Claude (pre_call guardrail)

PII ที่ detect:
  - เลขบัตรประชาชน 13 หลัก
  - เลขโทรศัพท์ไทย (08x, 09x, 06x)
  - อีเมล
  - เลขบัญชีธนาคาร
  - ชื่อ-นามสกุลภาษาไทย (heuristic: คำขึ้นต้นด้วย นาย/นาง/นางสาว/ดร.)
"""

import re
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# ── PII Patterns ──────────────────────────────────────────────
_PATTERNS = {
    "thai_national_id": re.compile(r"\b[0-9]{13}\b"),
    "thai_phone":       re.compile(r"\b0[689][0-9]{8}\b"),
    "email":            re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    "bank_account":     re.compile(r"\b[0-9]{10,12}\b"),
    "thai_name_prefix": re.compile(r"(นาย|นาง(?:สาว)?|ดร\.|Mr\.|Mrs\.|Miss)\s+[\u0E00-\u0E7F]+"),
}

# Action ต่อ PII type
_ACTIONS = {
    "thai_national_id": "blocked",   # บล็อกทันที
    "thai_name_prefix": "warned",    # เตือนแต่ไม่บล็อก
    "thai_phone":       "warned",
    "email":            "warned",
    "bank_account":     "warned",
}


class GuardrailRequest(BaseModel):
    """LiteLLM ส่ง request body นี้มา"""
    messages: list[dict]
    model: str
    user: str | None = None


class GuardrailResponse(BaseModel):
    success: bool
    action: str  # "allow" | "block"
    pii_detected: list[str]
    message: str | None = None


def _extract_text(messages: list[dict]) -> str:
    """รวม content ทุก message เป็น text เดียว"""
    parts = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
    return " ".join(parts)


@router.post("/pii-check", response_model=GuardrailResponse)
def pii_check(req: GuardrailRequest) -> GuardrailResponse:
    text = _extract_text(req.messages)
    detected: list[str] = []
    should_block = False

    for pii_type, pattern in _PATTERNS.items():
        if pattern.search(text):
            detected.append(pii_type)
            if _ACTIONS.get(pii_type) == "blocked":
                should_block = True

    if not detected:
        return GuardrailResponse(success=True, action="allow", pii_detected=[])

    if should_block:
        return GuardrailResponse(
            success=False,
            action="block",
            pii_detected=detected,
            message="พบข้อมูลส่วนบุคคลที่มีความละเอียดอ่อน (เลขบัตรประชาชน) กรุณาลบออกก่อนส่ง",
        )

    # warned: อนุญาตแต่บันทึก log
    return GuardrailResponse(
        success=True,
        action="allow",
        pii_detected=detected,
        message="พบข้อมูลที่อาจเป็น PII กรุณาระวังการแชร์ข้อมูลส่วนบุคคล",
    )
