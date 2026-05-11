"""Billing Service — Cost report ต่อ user/department (หน่วย ฿)

อ่านข้อมูลจาก LiteLLM spend logs (ผ่าน API) แล้วแปลงเป็น THB
Exchange rate: $1 USD = 35 THB (อัปเดตรายเดือนโดย admin)
"""

import os
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Annotated
import httpx

from src.auth.router import get_current_user, UserInfo

router = APIRouter()

LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://litellm:4000")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")
USD_TO_THB = 35.0  # อัปเดตรายเดือน


class UserSpend(BaseModel):
    user_id: str
    email: str
    department: str
    total_usd: float
    total_thb: float
    total_tokens: int
    period: str


class DeptSpend(BaseModel):
    department: str
    total_usd: float
    total_thb: float
    total_tokens: int
    user_count: int
    period: str


def _litellm_headers() -> dict:
    return {"Authorization": f"Bearer {LITELLM_MASTER_KEY}"}


@router.get("/my-usage", response_model=UserSpend)
async def my_usage(
    user: Annotated[UserInfo, Depends(get_current_user)],
    period: str = Query("monthly", description="monthly | weekly | daily"),
) -> UserSpend:
    """ดู usage ของตัวเอง"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{LITELLM_BASE_URL}/spend/users",
            headers=_litellm_headers(),
            params={"user_id": user.user_id},
        )
    data = resp.json() if resp.is_success else {}
    total_usd = data.get("spend", 0.0)
    total_tokens = data.get("total_tokens", 0)
    return UserSpend(
        user_id=user.user_id,
        email=user.email,
        department=user.department,
        total_usd=total_usd,
        total_thb=round(total_usd * USD_TO_THB, 2),
        total_tokens=total_tokens,
        period=period,
    )


@router.get("/department", response_model=list[DeptSpend])
async def dept_report(
    user: Annotated[UserInfo, Depends(get_current_user)],
    period: str = Query("monthly"),
) -> list[DeptSpend]:
    """รายงาน cost ต่อ department (admin เท่านั้น)"""
    if user.tier != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin only")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{LITELLM_BASE_URL}/spend/tags",
            headers=_litellm_headers(),
        )
    raw = resp.json() if resp.is_success else []

    # group by department tag
    dept_map: dict[str, dict] = {}
    for item in raw:
        dept = item.get("tag", "Unknown")
        if dept not in dept_map:
            dept_map[dept] = {"usd": 0.0, "tokens": 0, "users": set()}
        dept_map[dept]["usd"] += item.get("spend", 0.0)
        dept_map[dept]["tokens"] += item.get("total_tokens", 0)
        dept_map[dept]["users"].add(item.get("user_id", ""))

    return [
        DeptSpend(
            department=dept,
            total_usd=round(v["usd"], 4),
            total_thb=round(v["usd"] * USD_TO_THB, 2),
            total_tokens=v["tokens"],
            user_count=len(v["users"]),
            period=period,
        )
        for dept, v in dept_map.items()
    ]


@router.get("/exchange-rate")
def exchange_rate() -> dict:
    """ดู USD/THB rate ปัจจุบัน"""
    return {"usd_to_thb": USD_TO_THB, "note": "อัปเดตรายเดือนโดย admin"}
